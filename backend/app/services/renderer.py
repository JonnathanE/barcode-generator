"""Barcode rendering with BWIPP + Ghostscript, entirely in memory.

Pipeline (PLAN.md §5.3, option A):

1. Build a PostScript program: the BWIPP library (``barcode.ps`` shipped with
   ``treepoem``) plus the encoder invocation.
2. ``gs -sDEVICE=eps2write`` flattens it into a small vector EPS with a tight
   ``%%BoundingBox``. For the downloadable EPS, text is converted to outlines
   (``-dNoOutputFonts``) so print shops don't depend on font substitution.
3. For PNG, that EPS is rasterized with ``pnggray`` at the requested DPI.

Every Ghostscript call uses ``-dSAFER``, stdin/stdout (no temp files) and a timeout.
"""

import shutil
import subprocess
from binascii import hexlify
from dataclasses import dataclass
from functools import cache
from importlib import resources

from app.core.config import get_settings

GS1_MODULE_MM = 0.33
"""Nominal EAN-13 module width (X-dimension) at 100 % magnification."""

_BWIPP_MODULE_MM = 25.4 / 72
"""BWIPP draws one module per PostScript point."""

_PAGE_POINTS = 3000
_ORIGIN_POINTS = 200

_GS_BASE_ARGS = ("-dSAFER", "-dQUIET", "-dNOPAUSE", "-dBATCH")

_PROGRAM_TEMPLATE = """\
%!PS
{bwipp}
/Helvetica findfont 10 scalefont setfont
{{
  {origin} {origin} translate
  {magnification} {magnification} scale
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


class RenderError(Exception):
    """Ghostscript or BWIPP failed to produce the barcode."""


@dataclass(frozen=True, slots=True)
class RenderOptions:
    include_text: bool = True
    scale: int = 2
    bar_height_mm: float = 22.85
    dpi: int = 300

    @property
    def magnification(self) -> float:
        """PostScript scale factor so that one module is ``GS1_MODULE_MM * scale``."""
        return self.scale * GS1_MODULE_MM / _BWIPP_MODULE_MM


def render_ean13_eps(code: str, options: RenderOptions) -> bytes:
    """Vector EPS with text converted to outlines."""
    return _render_eps("ean13", code, _ean13_bwipp_options(options), options, outline_text=True)


def render_ean13_png(code: str, options: RenderOptions) -> bytes:
    """Grayscale PNG at ``options.dpi`` (stored in the ``pHYs`` chunk)."""
    eps = _render_eps("ean13", code, _ean13_bwipp_options(options), options, outline_text=False)
    return _run_ghostscript(
        "-sDEVICE=pnggray",
        "-dEPSCrop",
        f"-r{options.dpi}",
        # Antialias text only: bars stay crisp, which scanners prefer.
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=1",
        stdin=eps,
    )


def _ean13_bwipp_options(options: RenderOptions) -> dict[str, str | bool]:
    # BWIPP's height is in inches and gets multiplied by the magnification,
    # so divide it out to obtain the requested physical bar height.
    height_in = options.bar_height_mm / 25.4 / options.magnification
    return {"includetext": options.include_text, "height": f"{height_in:.6f}"}


def _render_eps(
    encoder: str,
    data: str,
    bwipp_options: dict[str, str | bool],
    options: RenderOptions,
    *,
    outline_text: bool,
) -> bytes:
    program = _PROGRAM_TEMPLATE.format(
        bwipp=_load_bwipp(),
        origin=_ORIGIN_POINTS,
        magnification=f"{options.magnification:.6f}",
        data=_ps_hex_string(data),
        options=_ps_hex_string(_format_bwipp_options(bwipp_options)),
        encoder=_ps_hex_string(encoder),
    )
    return _run_ghostscript(
        "-sDEVICE=eps2write",
        f"-dDEVICEWIDTHPOINTS={_PAGE_POINTS}",
        f"-dDEVICEHEIGHTPOINTS={_PAGE_POINTS}",
        *(("-dNoOutputFonts",) if outline_text else ()),
        stdin=program.encode("ascii"),
    )


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


# BWIPP is passed inline because SAFER mode forbids the PS code from reading files.
@cache
def _load_bwipp() -> str:
    return (
        resources.files("treepoem")
        .joinpath("postscriptbarcode/barcode.ps")
        .read_text(encoding="utf-8")
    )


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
