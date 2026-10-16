"""Barcode rendering with BWIPP + Ghostscript, entirely in memory.

Pipeline (PLAN.md §5.3, option A):

* The PostScript program is the minimal BWIPP subset for the encoder (``barcode.ps``
  shipped with ``treepoem``, filtered by its ``--REQUIRES`` metadata) plus one page
  per code. Starting Ghostscript and parsing BWIPP cost ~0.9 s on 0.1 CPU, drawing a
  code ~0.1 s, so batches render up to ``CODES_PER_PROCESS`` codes per process.
* Each page is exactly the symbol's extent including quiet zones (RF-06a), so the
  output needs no cropping and the background covers the quiet zones.
* EPS: ``gs -sDEVICE=ps2write`` flattens the pages into vector paths; text is
  converted to outlines (``-dNoOutputFonts``) so print shops don't depend on font
  substitution. eps2write refuses multi-page output to stdout, so the ps2write
  document is split into one EPS per page: same prolog with eps2write's two flags,
  which yields what eps2write would have produced. Exact physical size.
* PNG: ``pnggray`` pages (black on white), split by PNG chunks and colorized with
  Pillow using the ink coverage as mask, so antialiased text edges stay right on any
  background, transparent included. Modules are snapped to whole pixels (and BWIPP's
  ink spread is disabled) so bars don't get uneven widths at low DPI.

Every Ghostscript call uses ``-dSAFER``, stdin/stdout (no temp files) and a timeout.
"""

import io
import math
import re
import shutil
import struct
import subprocess
from binascii import hexlify
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources
from itertools import batched

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.symbologies.base import (
    MM_PER_POINT,
    TRANSPARENT,
    OutputFormat,
    RenderOptions,
    Symbology,
)

CODES_PER_PROCESS = 100
"""Bounds Ghostscript memory and the work lost if one call fails."""

_GS_BASE_ARGS = ("-dSAFER", "-dQUIET", "-dNOPAUSE", "-dBATCH")

_PROGRAM_HEADER = "%!PS\n{bwipp}\n/Helvetica findfont 10 scalefont setfont\n"

# One page per code. On a BWIPP error the page is still emitted (blank) so the page
# count stays aligned with the codes; the error goes to stderr and fails the call.
_PAGE_TEMPLATE = """\
gsave
{background}
{{
  {origin_x} {origin_y} translate
  {module_points} {module_points} scale
  0 0 moveto
  {data} {options} {encoder} cvn
  /uk.co.terryburton.bwipp findresource exec
}} stopped {{
  $error /errorname get dup length string cvs 0 6 getinterval (bwipp.) ne {{ stop }} if
  (%stderr) (w) file
  dup (BWIPP ERROR: ) writestring
  dup $error /errorname get dup length string cvs writestring
  dup ( ) writestring
  dup $error /errorinfo get dup length string cvs writestring
  dup (\\n) writestring
  flushfile
}} if
grestore
showpage
"""

_BWIPP_BLOCK = re.compile(
    r"^% --BEGIN (RESOURCE|ENCODER|RENDERER) (\w+)--\n.*?^% --END \1 \2--\n", re.S | re.M
)
_BWIPP_REQUIRES = re.compile(r"^% --REQUIRES ([\w ]+)--$", re.M)
_EPS_BOUNDING_BOX = re.compile(rb"^%%(HiRes)?BoundingBox: .*$", re.M)
_PS_PAGE = re.compile(rb"^%%Page: \d+ \d+\n", re.M)
_PS_PAGE_BOUNDING_BOX = re.compile(rb"^%%PageBoundingBox: .*\n", re.M)
_PS_PAGES = re.compile(rb"^%%Pages: \d+$", re.M)
# ps2write vs eps2write prolog: the only differences (checked on Ghostscript 10.0x).
_EPS_PROLOG_FLAGS = (
    (b"/SetPageSize true def", b"/SetPageSize false def"),
    (b"/EPS2Write false def", b"/EPS2Write true def"),
)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class RenderError(Exception):
    """Ghostscript or BWIPP failed to produce the barcode."""


def render(symbology: Symbology, code: str, fmt: OutputFormat, options: RenderOptions) -> bytes:
    """Render an already normalized ``code``. Blocking: call it from a threadpool."""
    return next(render_many(symbology, [code], fmt, options))


def render_many(
    symbology: Symbology, codes: Sequence[str], fmt: OutputFormat, options: RenderOptions
) -> Iterator[bytes]:
    """Render normalized ``codes`` in order, one Ghostscript process per chunk.

    Lazy: files are produced chunk by chunk, so a ZIP can be written without holding
    every file in memory. Blocking: consume it from a threadpool.
    """
    for chunk in batched(codes, CODES_PER_PROCESS):
        match fmt:
            case OutputFormat.PNG:
                yield from _render_png(symbology, chunk, options)
            case OutputFormat.EPS:
                yield from _render_eps(symbology, chunk, options)


def _render_eps(
    symbology: Symbology, codes: Sequence[str], options: RenderOptions
) -> Iterator[bytes]:
    module_points = symbology.module_mm * options.scale / MM_PER_POINT
    extent = symbology.extent(options, module_points)
    width = extent.width * module_points
    height = extent.height * module_points
    bar_color = options.bar_color.removeprefix("#").upper()

    program = _build_program(
        symbology,
        codes,
        {
            **symbology.bwipp_options(options, module_points),
            "barcolor": bar_color,
            "textcolor": bar_color,
        },
        module_points=module_points,
        origin=(-extent.left * module_points, -extent.bottom * module_points),
        background=_ps_background(options.background, width, height),
    )
    document = _run_ghostscript(
        "-sDEVICE=ps2write",
        f"-dDEVICEWIDTHPOINTS={width:.4f}",
        f"-dDEVICEHEIGHTPOINTS={height:.4f}",
        "-dNoOutputFonts",
        stdin=program,
        codes=len(codes),
    )
    for eps in _split_ps_document(document, len(codes)):
        # The box covers the whole page so the quiet zones are part of the file even
        # with a transparent background.
        yield _set_bounding_box(eps, width, height)


@dataclass(frozen=True, slots=True)
class _PngGeometry:
    module_points: float
    left_px: int
    bottom_px: int
    width_px: int
    height_px: int


def _png_geometry(symbology: Symbology, options: RenderOptions) -> _PngGeometry:
    dpi = options.dpi
    module_px = max(1, round(symbology.module_mm * options.scale / 25.4 * dpi))
    module_points = module_px * 72 / dpi
    extent = symbology.extent(options, module_points)
    left_px = math.floor(extent.left * module_px)
    bottom_px = math.floor(extent.bottom * module_px)
    return _PngGeometry(
        module_points=module_points,
        left_px=left_px,
        bottom_px=bottom_px,
        width_px=math.ceil(extent.right * module_px) - left_px,
        height_px=math.ceil(extent.top * module_px) - bottom_px,
    )


def png_size(symbology: Symbology, options: RenderOptions) -> tuple[int, int]:
    """Width and height in pixels of each PNG, without rendering anything."""
    geometry = _png_geometry(symbology, options)
    return geometry.width_px, geometry.height_px


def _render_png(
    symbology: Symbology, codes: Sequence[str], options: RenderOptions
) -> Iterator[bytes]:
    dpi = options.dpi
    geometry = _png_geometry(symbology, options)
    module_points = geometry.module_points

    program = _build_program(
        symbology,
        codes,
        {**symbology.bwipp_options(options, module_points), "inkspread": "0"},
        module_points=module_points,
        origin=(-geometry.left_px * 72 / dpi, -geometry.bottom_px * 72 / dpi),
        background="",
    )
    raster = _run_ghostscript(
        "-sDEVICE=pnggray",
        f"-r{dpi}",
        f"-g{geometry.width_px}x{geometry.height_px}",
        # Antialias text only: bars stay crisp, which scanners prefer.
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=1",
        stdin=program,
        codes=len(codes),
    )
    pages = _split_pngs(raster)
    if len(pages) != len(codes):
        raise RenderError(f"Ghostscript generó {len(pages)} imágenes para {len(codes)} códigos")
    for page in pages:
        yield _colorize_png(page, options)


def _build_program(
    symbology: Symbology,
    codes: Sequence[str],
    bwipp_options: dict[str, str | bool],
    *,
    module_points: float,
    origin: tuple[float, float],
    background: str,
) -> bytes:
    options = _ps_hex_string(_format_bwipp_options(bwipp_options))
    encoder = _ps_hex_string(symbology.bwipp_name)
    pages = (
        _PAGE_TEMPLATE.format(
            background=background,
            origin_x=f"{origin[0]:.6f}",
            origin_y=f"{origin[1]:.6f}",
            module_points=f"{module_points:.6f}",
            data=_ps_hex_string(code),
            options=options,
            encoder=encoder,
        )
        for code in codes
    )
    header = _PROGRAM_HEADER.format(bwipp=_load_bwipp(symbology.bwipp_name))
    return (header + "".join(pages)).encode("ascii")


def _run_ghostscript(*device_args: str, stdin: bytes, codes: int = 1) -> bytes:
    # The base timeout covers ~10 codes; bigger chunks get proportionally more time.
    timeout = get_settings().ghostscript_timeout_seconds * max(1.0, codes / 10)
    args = [_ghostscript_binary(), *_GS_BASE_ARGS, *device_args, "-sOutputFile=-", "-"]
    try:
        # Fixed argv (no shell) and SAFER mode; user data only travels hex-encoded on stdin.
        result = subprocess.run(  # noqa: S603
            args, input=stdin, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"Ghostscript superó el tiempo límite de {timeout:g} s") from exc

    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0 or "BWIPP ERROR:" in stderr or not result.stdout:
        raise RenderError(stderr or f"Ghostscript terminó con código {result.returncode}")
    return result.stdout


def _split_ps_document(document: bytes, count: int) -> list[bytes]:
    """Split a multi-page ps2write document into single-page EPS files."""
    try:
        prolog_start = document.index(b"%%BeginProlog")
        prolog_end = document.index(b"%%EndProlog\n") + len(b"%%EndProlog\n")
        trailer_start = document.rindex(b"%%Trailer")
    except ValueError as exc:
        raise RenderError("Estructura inesperada de la salida de ps2write") from exc

    header = document[:prolog_start]
    if not header.startswith(b"%!PS-Adobe-3.0\n"):
        raise RenderError("Cabecera inesperada de la salida de ps2write")
    header = b"%!PS-Adobe-3.0 EPSF-3.0\n" + header.removeprefix(b"%!PS-Adobe-3.0\n")
    header = _PS_PAGES.sub(b"%%Pages: 1", header)

    prolog = document[prolog_start:prolog_end]
    for ps2write_flag, eps2write_flag in _EPS_PROLOG_FLAGS:
        if prolog.count(ps2write_flag) != 1:
            raise RenderError("Prolog inesperado de ps2write")
        prolog = prolog.replace(ps2write_flag, eps2write_flag)

    pages = _PS_PAGE.split(document[prolog_end:trailer_start])[1:]
    if len(pages) != count:
        raise RenderError(f"ps2write generó {len(pages)} páginas para {count} códigos")
    trailer = document[trailer_start:]
    return [
        header + prolog + b"%%Page: 1 1\n" + _PS_PAGE_BOUNDING_BOX.sub(b"", page) + trailer
        for page in pages
    ]


def _split_pngs(data: bytes) -> list[bytes]:
    """Split concatenated PNG files by walking their length-prefixed chunks."""
    files: list[bytes] = []
    position = 0
    while position < len(data):
        if data[position : position + 8] != _PNG_SIGNATURE:
            raise RenderError("Salida PNG inesperada de Ghostscript")
        cursor = position + 8
        while True:
            if cursor + 8 > len(data):
                raise RenderError("PNG truncado en la salida de Ghostscript")
            (length,) = struct.unpack(">I", data[cursor : cursor + 4])
            chunk_type = data[cursor + 4 : cursor + 8]
            cursor += 12 + length  # length + type + data + CRC
            if chunk_type == b"IEND":
                break
        files.append(data[position:cursor])
        position = cursor
    return files


def _ps_background(background: str, width: float, height: float) -> str:
    if background == TRANSPARENT:
        return ""
    r, g, b = (channel / 255 for channel in _hex_to_rgb(background))
    return f"{r:.4f} {g:.4f} {b:.4f} setrgbcolor 0 0 {width:.4f} {height:.4f} rectfill"


def _set_bounding_box(eps: bytes, width: float, height: float) -> bytes:
    def replace(match: re.Match[bytes]) -> bytes:
        if match.group(1):
            return f"%%HiResBoundingBox: 0 0 {width:.4f} {height:.4f}".encode()
        return f"%%BoundingBox: 0 0 {math.ceil(width)} {math.ceil(height)}".encode()

    header, separator, body = eps.partition(b"%%EndComments")
    return _EPS_BOUNDING_BOX.sub(replace, header) + separator + body


def _colorize_png(raster: bytes, options: RenderOptions) -> bytes:
    if options.bar_color.upper() == "#000000" and options.background.upper() == "#FFFFFF":
        # Ghostscript's grayscale PNG already carries the DPI (pHYs); decoding and
        # re-encoding it would double the time of large batches.
        return raster
    gray = Image.open(io.BytesIO(raster)).convert("L")
    ink = ImageOps.invert(gray)  # 255 where fully inked
    bars = Image.new("RGB", gray.size, _hex_to_rgb(options.bar_color))
    image: Image.Image
    if options.background == TRANSPARENT:
        image = bars.convert("RGBA")
        image.putalpha(ink)
    else:
        paper = Image.new("RGB", gray.size, _hex_to_rgb(options.background))
        image = Image.composite(bars, paper, ink)

    output = io.BytesIO()
    image.save(output, format="PNG", dpi=(options.dpi, options.dpi))
    return output.getvalue()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.removeprefix("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


# BWIPP is passed inline because SAFER mode forbids the PS code from reading files.
@cache
def _load_bwipp(encoder: str) -> str:
    """BWIPP resources needed by ``encoder``, in library order (dependencies first)."""
    library = (
        resources.files("treepoem")
        .joinpath("postscriptbarcode/barcode.ps")
        .read_text(encoding="utf-8")
    )
    blocks = {match.group(2): match.group(0) for match in _BWIPP_BLOCK.finditer(library)}

    needed: set[str] = set()
    pending = [encoder]
    while pending:
        name = pending.pop()
        if name in needed:
            continue
        if name not in blocks:
            raise RenderError(f"Recurso BWIPP desconocido: {name}")
        needed.add(name)
        if requires := _BWIPP_REQUIRES.search(blocks[name]):
            pending.extend(requires.group(1).split())

    return "".join(block for name, block in blocks.items() if name in needed)


@cache
def _ghostscript_binary() -> str:
    binary = shutil.which("gs")
    if binary is None:
        raise RenderError("Ghostscript (gs) no está instalado")
    return binary


def _format_bwipp_options(options: dict[str, str | bool]) -> str:
    items: list[str] = []
    for name, value in options.items():
        if isinstance(value, bool):
            if value:
                items.append(name)
        else:
            items.append(f"{name}={value}")
    return " ".join(items)


def _ps_hex_string(text: str) -> str:
    """PostScript hex string: user input can't break out of the literal."""
    return f"<{hexlify(text.encode('utf-8')).decode('ascii')}>"
