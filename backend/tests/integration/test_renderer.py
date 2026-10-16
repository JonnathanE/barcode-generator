import io
import re
import shutil
import subprocess
from typing import Any

import pytest
import zxingcpp
from PIL import Image

from app.core.config import get_settings
from app.services.renderer import (
    GS1_MODULE_MM,
    RenderError,
    RenderOptions,
    _load_bwipp,
    render_ean13_eps,
    render_ean13_png,
)

pytestmark = pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript no instalado")

CODE = "7861234567898"
EAN13_MODULES = 95
POINTS_TO_MM = 25.4 / 72

# Operators allowed in the page content (PDF content-stream syntax): graphics state,
# color, path construction, painting and clipping. Images (BI/ID/EI, Do) are excluded.
VECTOR_OPERATORS = {
    *("q", "Q", "cm", "w", "J", "j", "M", "d", "i"),
    *("g", "G", "rg", "RG", "k", "K"),
    *("m", "l", "c", "v", "y", "h", "re"),
    *("f", "f*", "F", "S", "s", "B", "B*", "b", "b*", "n", "W", "W*"),
}
OPERATOR_TOKEN = re.compile(rb"(?<![/\w.\-])([A-Za-z*'\"]+)(?![\w.\-])")


def decode(png: bytes) -> list[str]:
    image = Image.open(io.BytesIO(png))
    return [
        r.text for r in zxingcpp.read_barcodes(image) if r.format == zxingcpp.BarcodeFormat.EAN13
    ]


def eps_bounding_box_mm(eps: bytes) -> tuple[float, float]:
    match = re.search(rb"^%%HiResBoundingBox: ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)", eps, re.M)
    assert match is not None
    x1, y1, x2, y2 = (float(n) for n in match.groups())
    return (x2 - x1) * POINTS_TO_MM, (y2 - y1) * POINTS_TO_MM


def page_content(eps: bytes) -> bytes:
    """Content stream of the page (the prolog is eps2write's generic procset)."""
    match = re.search(rb"stream\r?\n(.*?)endstream", eps.split(b"%%EndProlog", 1)[1], re.S)
    assert match is not None
    return match.group(1)


# ---------- PNG ----------


@pytest.mark.parametrize("include_text", [True, False])
@pytest.mark.parametrize("scale", [1, 2, 5])
@pytest.mark.parametrize("dpi", [150, 300, 600])
def test_png_decodes_for_every_option_combination(include_text: bool, scale: int, dpi: int) -> None:
    options = RenderOptions(include_text=include_text, scale=scale, dpi=dpi)

    assert decode(render_ean13_png(CODE, options)) == [CODE]


@pytest.mark.parametrize(("scale", "dpi"), [(1, 150), (2, 300), (3, 600)])
def test_png_modules_are_whole_pixels_and_size_follows_options(scale: int, dpi: int) -> None:
    options = RenderOptions(include_text=False, scale=scale, dpi=dpi, bar_height_mm=30)

    image = Image.open(io.BytesIO(render_ean13_png(CODE, options)))

    module_px = round(GS1_MODULE_MM * scale / 25.4 * dpi)
    assert image.width == EAN13_MODULES * module_px
    # Snapping keeps the physical size close to the requested one.
    assert image.width / dpi * 25.4 == pytest.approx(
        EAN13_MODULES * GS1_MODULE_MM * scale, rel=0.03
    )
    assert image.height == pytest.approx(30 / 25.4 * dpi, abs=1)
    # PNG stores whole pixels per metre, so 150 dpi reads back as ~150.012.
    assert image.info["dpi"] == pytest.approx((dpi, dpi), abs=0.05)


def test_png_dpi_changes_resolution_not_physical_size() -> None:
    low = Image.open(io.BytesIO(render_ean13_png(CODE, RenderOptions(dpi=150))))
    high = Image.open(io.BytesIO(render_ean13_png(CODE, RenderOptions(dpi=600))))

    assert high.width / low.width == pytest.approx(4, rel=0.02)


# ---------- EPS ----------


def test_eps_has_epsf_header_and_bounding_box() -> None:
    eps = render_ean13_eps(CODE, RenderOptions())

    assert eps.startswith(b"%!PS-Adobe-3.0 EPSF-3.0")
    assert re.search(rb"^%%BoundingBox: \d+ \d+ \d+ \d+$", eps, re.M)


@pytest.mark.parametrize("include_text", [True, False])
def test_eps_page_is_pure_vector(include_text: bool) -> None:
    content = page_content(render_ean13_eps(CODE, RenderOptions(include_text=include_text)))

    operators = {token.decode() for token in OPERATOR_TOKEN.findall(content)}
    assert operators <= VECTOR_OPERATORS, (
        f"operadores no vectoriales: {operators - VECTOR_OPERATORS}"
    )
    assert "re" in operators  # the bars


def test_eps_has_no_fonts_text_is_outlined() -> None:
    eps = render_ean13_eps(CODE, RenderOptions(include_text=True))

    assert b"/BaseFont" not in eps.split(b"%%EndProlog", 1)[1]


@pytest.mark.parametrize("scale", [1, 2, 5])
def test_eps_physical_size_follows_scale_and_bar_height(scale: int) -> None:
    eps = render_ean13_eps(CODE, RenderOptions(include_text=False, scale=scale, bar_height_mm=30))

    width_mm, height_mm = eps_bounding_box_mm(eps)
    assert width_mm == pytest.approx(EAN13_MODULES * GS1_MODULE_MM * scale, rel=0.01)
    assert height_mm == pytest.approx(30, abs=0.1)


def test_eps_rasterized_decodes_to_expected_code() -> None:
    eps = render_ean13_eps(CODE, RenderOptions())
    png = subprocess.run(
        ["gs", "-dSAFER", "-dQUIET", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pnggray", "-dEPSCrop",
         "-r300", "-sOutputFile=-", "-"],
        input=eps, capture_output=True, check=True, timeout=20,
    ).stdout  # fmt: skip

    assert decode(png) == [CODE]


# ---------- Errors and Ghostscript invocation ----------


def test_invalid_data_raises_render_error() -> None:
    with pytest.raises(RenderError, match="BWIPP ERROR"):
        render_ean13_eps("ABC", RenderOptions())


def test_timeout_raises_render_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ghostscript_timeout_seconds", 0.001)

    with pytest.raises(RenderError, match="tiempo límite"):
        render_ean13_eps(CODE, RenderOptions())


def test_ghostscript_uses_safer_stdio_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    real_run = subprocess.run

    def spy(args: list[str], **kwargs: Any) -> Any:
        calls.append({"args": args, **kwargs})
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    render_ean13_png(CODE, RenderOptions())
    render_ean13_eps(CODE, RenderOptions())

    assert len(calls) == 2  # one Ghostscript process per file
    for call in calls:
        assert "-dSAFER" in call["args"]
        assert call["args"][-2:] == ["-sOutputFile=-", "-"]
        assert call["timeout"] == get_settings().ghostscript_timeout_seconds
        assert call["input"]


# ---------- BWIPP subset ----------


def test_bwipp_subset_contains_encoder_and_its_dependencies_only() -> None:
    subset = _load_bwipp("ean13")

    for resource in ("preamble", "renlinear", "ean5", "ean2", "ean13"):
        assert re.search(rf"^% --BEGIN \w+ {resource}--$", subset, re.M), resource
    assert not re.search(r"^% --BEGIN \w+ qrcode--$", subset, re.M)
    assert len(subset) < 100_000  # vs ~1 MB for the full library


def test_bwipp_unknown_encoder_raises_render_error() -> None:
    with pytest.raises(RenderError, match="desconocido"):
        _load_bwipp("not-a-barcode")
