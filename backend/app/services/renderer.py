"""Barcode rendering with BWIPP + Ghostscript, entirely in memory.

Pipeline (PLAN.md §5.3, option A):

* The PostScript program is the minimal BWIPP subset for the encoder (``barcode.ps``
  shipped with ``treepoem``, filtered by its ``--REQUIRES`` metadata) plus the
  invocation. Parsing the full 1 MB library dominated render time on 0.1 CPU.
* The page is exactly the symbol's extent including quiet zones (RF-06a), so the
  output needs no cropping and the background covers the quiet zones.
* EPS: ``gs -sDEVICE=eps2write`` flattens the program into vector paths; text is
  converted to outlines (``-dNoOutputFonts``) so print shops don't depend on font
  substitution. Exact physical size.
* PNG: one ``pnggray`` pass (black on white), colorized afterwards with Pillow using
  the ink coverage as mask, so antialiased text edges stay right on any background,
  transparent included. Modules are snapped to whole pixels (and BWIPP's ink spread
  is disabled) so bars don't get uneven widths at low DPI.

Every Ghostscript call uses ``-dSAFER``, stdin/stdout (no temp files) and a timeout.
"""

import io
import math
import re
import shutil
import subprocess
from binascii import hexlify
from functools import cache
from importlib import resources

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.symbologies.base import (
    MM_PER_POINT,
    TRANSPARENT,
    OutputFormat,
    RenderOptions,
    Symbology,
)

_GS_BASE_ARGS = ("-dSAFER", "-dQUIET", "-dNOPAUSE", "-dBATCH")

_PROGRAM_TEMPLATE = """\
%!PS
{bwipp}
{background}
/Helvetica findfont 10 scalefont setfont
{{
  {origin_x} {origin_y} translate
  {module_points} {module_points} scale
  0 0 moveto
  {data} {options} {encoder} cvn
  /uk.co.terryburton.bwipp findresource exec
  showpage
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
"""

_BWIPP_BLOCK = re.compile(
    r"^% --BEGIN (RESOURCE|ENCODER|RENDERER) (\w+)--\n.*?^% --END \1 \2--\n", re.S | re.M
)
_BWIPP_REQUIRES = re.compile(r"^% --REQUIRES ([\w ]+)--$", re.M)
_EPS_BOUNDING_BOX = re.compile(rb"^%%(HiRes)?BoundingBox: .*$", re.M)


class RenderError(Exception):
    """Ghostscript or BWIPP failed to produce the barcode."""


def render(symbology: Symbology, code: str, fmt: OutputFormat, options: RenderOptions) -> bytes:
    """Render an already normalized ``code``. Blocking: call it from a threadpool."""
    match fmt:
        case OutputFormat.PNG:
            return _render_png(symbology, code, options)
        case OutputFormat.EPS:
            return _render_eps(symbology, code, options)


def _render_eps(symbology: Symbology, code: str, options: RenderOptions) -> bytes:
    module_points = symbology.module_mm * options.scale / MM_PER_POINT
    extent = symbology.extent(options, module_points)
    width = extent.width * module_points
    height = extent.height * module_points
    bar_color = options.bar_color.removeprefix("#").upper()

    program = _build_program(
        symbology,
        code,
        {
            **symbology.bwipp_options(options, module_points),
            "barcolor": bar_color,
            "textcolor": bar_color,
        },
        module_points=module_points,
        origin=(-extent.left * module_points, -extent.bottom * module_points),
        background=_ps_background(options.background, width, height),
    )
    eps = _run_ghostscript(
        "-sDEVICE=eps2write",
        f"-dDEVICEWIDTHPOINTS={width:.4f}",
        f"-dDEVICEHEIGHTPOINTS={height:.4f}",
        "-dNoOutputFonts",
        stdin=program,
    )
    # eps2write computes the box from the marks; widen it to the whole page so the
    # quiet zones are part of the file even with a transparent background.
    return _set_bounding_box(eps, width, height)


def _render_png(symbology: Symbology, code: str, options: RenderOptions) -> bytes:
    dpi = options.dpi
    module_px = max(1, round(symbology.module_mm * options.scale / 25.4 * dpi))
    module_points = module_px * 72 / dpi
    extent = symbology.extent(options, module_points)
    left_px = math.floor(extent.left * module_px)
    bottom_px = math.floor(extent.bottom * module_px)
    width_px = math.ceil(extent.right * module_px) - left_px
    height_px = math.ceil(extent.top * module_px) - bottom_px

    program = _build_program(
        symbology,
        code,
        {**symbology.bwipp_options(options, module_points), "inkspread": "0"},
        module_points=module_points,
        origin=(-left_px * 72 / dpi, -bottom_px * 72 / dpi),
        background="",
    )
    raster = _run_ghostscript(
        "-sDEVICE=pnggray",
        f"-r{dpi}",
        f"-g{width_px}x{height_px}",
        # Antialias text only: bars stay crisp, which scanners prefer.
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=1",
        stdin=program,
    )
    return _colorize_png(raster, options)


def _build_program(
    symbology: Symbology,
    data: str,
    bwipp_options: dict[str, str | bool],
    *,
    module_points: float,
    origin: tuple[float, float],
    background: str,
) -> bytes:
    return _PROGRAM_TEMPLATE.format(
        bwipp=_load_bwipp(symbology.bwipp_name),
        background=background,
        origin_x=f"{origin[0]:.6f}",
        origin_y=f"{origin[1]:.6f}",
        module_points=f"{module_points:.6f}",
        data=_ps_hex_string(data),
        options=_ps_hex_string(_format_bwipp_options(bwipp_options)),
        encoder=_ps_hex_string(symbology.bwipp_name),
    ).encode("ascii")


def _run_ghostscript(*device_args: str, stdin: bytes) -> bytes:
    timeout = get_settings().ghostscript_timeout_seconds
    args = [_ghostscript_binary(), *_GS_BASE_ARGS, *device_args, "-sOutputFile=-", "-"]
    try:
        # Fixed argv (no shell) and SAFER mode; user data only travels hex-encoded on stdin.
        result = subprocess.run(  # noqa: S603
            args, input=stdin, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"Ghostscript superó el tiempo límite de {timeout} s") from exc

    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0 or "BWIPP ERROR:" in stderr or not result.stdout:
        raise RenderError(stderr or f"Ghostscript terminó con código {result.returncode}")
    return result.stdout


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
    gray = Image.open(io.BytesIO(raster)).convert("L")
    image: Image.Image
    if options.bar_color.upper() == "#000000" and options.background.upper() == "#FFFFFF":
        image = gray  # default: keep the small 8-bit grayscale PNG
    else:
        ink = ImageOps.invert(gray)  # 255 where fully inked
        bars = Image.new("RGB", gray.size, _hex_to_rgb(options.bar_color))
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
