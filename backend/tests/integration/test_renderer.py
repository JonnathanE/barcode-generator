import io
import re
import shutil
import subprocess
from typing import Any

import pytest
import zxingcpp
from PIL import Image

from app.core.config import get_settings
from app.services import renderer
from app.services.renderer import RenderError, _load_bwipp, render, render_many
from app.symbologies.base import OutputFormat, RenderOptions
from app.symbologies.registry import registry

pytestmark = pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript no instalado")

EAN13 = registry.get("ean13")
CODE = "7861234567898"
MODULE_MM = 0.33
POINTS_TO_MM = 25.4 / 72
# Symbol width in modules including quiet zones: 11 + 95 + 7, plus 1 for the ">" guard.
WIDTH_MODULES = {True: 114, False: 113}

# Operators allowed in the page content (PDF content-stream syntax): graphics state,
# color, path construction, painting and clipping. Images (BI/ID/EI, Do) are excluded.
VECTOR_OPERATORS = {
    *("q", "Q", "cm", "w", "J", "j", "M", "d", "i", "setstrokeadjust", "true", "false"),
    *("g", "G", "rg", "RG", "k", "K"),
    *("m", "l", "c", "v", "y", "h", "re"),
    *("f", "f*", "F", "S", "s", "B", "B*", "b", "b*", "n", "W", "W*"),
}
OPERATOR_TOKEN = re.compile(rb"(?<![/\w.\-])([A-Za-z*'\"]+)(?![\w.\-])")


def png(options: RenderOptions) -> Image.Image:
    return Image.open(io.BytesIO(render(EAN13, CODE, OutputFormat.PNG, options)))


def eps(options: RenderOptions) -> bytes:
    return render(EAN13, CODE, OutputFormat.EPS, options)


def decode(image: Image.Image) -> list[str]:
    if image.mode == "RGBA":  # flatten transparency onto white, like a label would
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.getchannel("A"))
        image = flat
    results = zxingcpp.read_barcodes(image)
    return [r.text for r in results if r.format == zxingcpp.BarcodeFormat.EAN13]


def gray_row(image: Image.Image, y: int) -> bytes:
    """Gray levels (0 = ink, 255 = paper) of one pixel row."""
    gray = image.convert("L")
    return gray.tobytes()[y * gray.width : (y + 1) * gray.width]


def color_at(image: Image.Image, xy: tuple[int, int]) -> tuple[int, ...]:
    value = image.getpixel(xy)
    assert isinstance(value, tuple)
    return value


def module_px(scale: int, dpi: int) -> int:
    return round(MODULE_MM * scale / 25.4 * dpi)


def eps_bounding_box(data: bytes) -> tuple[float, float, float, float]:
    match = re.search(rb"^%%HiResBoundingBox: (\S+) (\S+) (\S+) (\S+)$", data, re.M)
    assert match is not None
    x1, y1, x2, y2 = (float(n) for n in match.groups())
    return x1, y1, x2, y2


def page_content(data: bytes) -> bytes:
    """Content stream of the page (the prolog is eps2write's generic procset)."""
    match = re.search(rb"stream\r?\n(.*?)endstream", data.split(b"%%EndProlog", 1)[1], re.S)
    assert match is not None
    return match.group(1)


def fill_colors(data: bytes) -> set[tuple[float, ...]]:
    content = page_content(data)
    rgb = re.findall(rb"([\d.]+) ([\d.]+) ([\d.]+) rg\b", content)
    gray = re.findall(rb"(?<![\d.] )([\d.]+) g\b", content)
    colors = {tuple(round(float(v), 2) for v in triple) for triple in rgb}
    colors |= {(round(float(v), 2),) * 3 for v in gray}
    return colors


def rasterize(data: bytes, dpi: int = 300) -> Image.Image:
    raster = subprocess.run(
        ["gs", "-dSAFER", "-dQUIET", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", "-dEPSCrop",
         f"-r{dpi}", "-sOutputFile=-", "-"],
        input=data, capture_output=True, check=True, timeout=20,
    ).stdout  # fmt: skip
    return Image.open(io.BytesIO(raster))


# ---------- PNG ----------


@pytest.mark.parametrize("include_text", [True, False])
@pytest.mark.parametrize("scale", [1, 2, 5])
@pytest.mark.parametrize("dpi", [150, 300, 600])
def test_png_decodes_for_every_option_combination(include_text: bool, scale: int, dpi: int) -> None:
    image = png(RenderOptions(include_text=include_text, scale=scale, dpi=dpi))

    assert decode(image) == [CODE]


@pytest.mark.parametrize("include_text", [True, False])
@pytest.mark.parametrize(("scale", "dpi"), [(1, 150), (2, 300), (3, 600)])
def test_png_size_includes_quiet_zones_in_whole_pixel_modules(
    include_text: bool, scale: int, dpi: int
) -> None:
    image = png(RenderOptions(include_text=include_text, scale=scale, dpi=dpi))

    assert image.width == WIDTH_MODULES[include_text] * module_px(scale, dpi)
    # PNG stores whole pixels per metre, so 150 dpi reads back as ~150.012.
    assert image.info["dpi"] == pytest.approx((dpi, dpi), abs=0.05)


def test_png_bar_height_is_physical() -> None:
    image = png(RenderOptions(include_text=False, scale=3, bar_height_mm=30, dpi=600))

    assert image.height == pytest.approx(30 / 25.4 * 600, abs=1)


@pytest.mark.parametrize("include_text", [True, False])
def test_png_quiet_zones_are_blank(include_text: bool) -> None:
    options = RenderOptions(include_text=include_text, scale=2, dpi=300)
    image = png(options)
    module = module_px(2, 300)
    pixels = gray_row(image, image.height // 4)  # crosses the bars, above the digits

    assert all(p == 255 for p in pixels[: 11 * module]), "zona de silencio izquierda"
    assert all(p == 255 for p in pixels[(11 + 95) * module :]), "zona de silencio derecha"
    assert pixels[11 * module] == 0  # first guard bar starts right after it


def test_png_default_colors_are_grayscale() -> None:
    assert png(RenderOptions()).mode == "L"


def test_png_custom_bar_and_background_colors() -> None:
    image = png(RenderOptions(bar_color="#1F3A93", background="#FFF8DC")).convert("RGB")
    module = module_px(2, 300)

    assert color_at(image, (0, 0)) == (0xFF, 0xF8, 0xDC)
    assert color_at(image, (11 * module, image.height // 4)) == (0x1F, 0x3A, 0x93)
    assert decode(image) == [CODE]


def test_png_transparent_background() -> None:
    image = png(RenderOptions(bar_color="#1F3A93", background="transparent"))
    module = module_px(2, 300)

    assert image.mode == "RGBA"
    assert color_at(image, (0, 0))[3] == 0
    assert color_at(image, (11 * module, image.height // 4)) == (0x1F, 0x3A, 0x93, 255)
    assert decode(image) == [CODE]


def test_png_dpi_changes_resolution_not_physical_size() -> None:
    low, high = png(RenderOptions(dpi=150)), png(RenderOptions(dpi=600))

    assert high.width / low.width == pytest.approx(4, rel=0.03)


# ---------- EPS ----------


def test_eps_has_epsf_header_and_bounding_box_at_origin() -> None:
    data = eps(RenderOptions())

    assert data.startswith(b"%!PS-Adobe-3.0 EPSF-3.0")
    assert re.search(rb"^%%BoundingBox: 0 0 \d+ \d+$", data, re.M)
    assert eps_bounding_box(data)[:2] == (0, 0)


@pytest.mark.parametrize(
    "options",
    [
        RenderOptions(include_text=True),
        RenderOptions(include_text=False),
        RenderOptions(bar_color="#1F3A93", background="#FFF8DC"),
        RenderOptions(background="transparent"),
    ],
)
def test_eps_page_is_pure_vector(options: RenderOptions) -> None:
    content = page_content(eps(options))

    operators = {token.decode() for token in OPERATOR_TOKEN.findall(content)}
    non_vector = operators - VECTOR_OPERATORS
    assert not non_vector, f"operadores no vectoriales: {non_vector}"
    assert "re" in operators  # the bars


def test_eps_has_no_fonts_text_is_outlined() -> None:
    data = eps(RenderOptions(include_text=True))

    assert b"/BaseFont" not in data.split(b"%%EndProlog", 1)[1]


@pytest.mark.parametrize("include_text", [True, False])
@pytest.mark.parametrize("scale", [1, 2, 5])
def test_eps_physical_size_includes_quiet_zones(include_text: bool, scale: int) -> None:
    options = RenderOptions(include_text=include_text, scale=scale, bar_height_mm=30)

    x1, y1, x2, y2 = eps_bounding_box(eps(options))

    width_mm = (x2 - x1) * POINTS_TO_MM
    height_mm = (y2 - y1) * POINTS_TO_MM
    assert width_mm == pytest.approx(WIDTH_MODULES[include_text] * MODULE_MM * scale, rel=0.001)
    if not include_text:
        assert height_mm == pytest.approx(30, abs=0.01)


def test_eps_rasterized_decodes_and_has_blank_quiet_zones() -> None:
    image = rasterize(eps(RenderOptions(include_text=False, scale=2)), dpi=300)
    module = MODULE_MM * 2 / 25.4 * 300
    pixels = gray_row(image, image.height // 2)

    assert decode(image) == [CODE]
    assert all(p > 250 for p in pixels[: int(10.5 * module)])
    assert all(p > 250 for p in pixels[int(106.5 * module) :])


def test_eps_colors() -> None:
    colors = fill_colors(eps(RenderOptions(bar_color="#1F3A93", background="#FFFF00")))

    assert (1.0, 1.0, 0.0) in colors  # background
    assert (0.12, 0.23, 0.58) in colors  # bars and text


def test_eps_transparent_background_paints_only_bars() -> None:
    colors = fill_colors(eps(RenderOptions(background="transparent")))

    assert colors == {(0.0, 0.0, 0.0)}


# ---------- Errors and Ghostscript invocation ----------


def test_invalid_data_raises_render_error() -> None:
    with pytest.raises(RenderError, match="BWIPP ERROR"):
        render(EAN13, "ABC", OutputFormat.EPS, RenderOptions())


def test_timeout_raises_render_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ghostscript_timeout_seconds", 0.001)

    with pytest.raises(RenderError, match="tiempo límite"):
        eps(RenderOptions())


def test_ghostscript_uses_safer_stdio_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    real_run = subprocess.run

    def spy(args: list[str], **kwargs: Any) -> Any:
        calls.append({"args": args, **kwargs})
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    png(RenderOptions())
    eps(RenderOptions())

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


# ---------- Batches (render_many) ----------

BATCH = ["7861234567898", "4006381333931", "5901234123457", "9780306406157", "0000000000000"]


@pytest.mark.parametrize("fmt", list(OutputFormat))
def test_render_many_returns_one_file_per_code_in_order(fmt: OutputFormat) -> None:
    files = list(render_many(EAN13, BATCH, fmt, RenderOptions(scale=1)))

    assert len(files) == len(BATCH)
    for code, data in zip(BATCH, files, strict=True):
        image = Image.open(io.BytesIO(data)) if fmt is OutputFormat.PNG else rasterize(data)
        assert decode(image) == [code]


def test_render_many_eps_files_are_standalone_eps() -> None:
    files = list(render_many(EAN13, BATCH[:2], OutputFormat.EPS, RenderOptions()))

    for data in files:
        assert data.startswith(b"%!PS-Adobe-3.0 EPSF-3.0\n")
        assert re.search(rb"^%%Pages: 1$", data, re.M)
        assert data.count(b"%%Page: ") == 1
        assert b"/EPS2Write true def" in data and b"/SetPageSize false def" in data
        assert data.rstrip().endswith(b"%%EOF")


def test_render_many_uses_one_process_per_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renderer, "CODES_PER_PROCESS", 2)
    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy(args: list[str], **kwargs: Any) -> Any:
        calls.append(args)
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    files = list(render_many(EAN13, BATCH, OutputFormat.PNG, RenderOptions(scale=1)))

    assert len(calls) == 3  # 2 + 2 + 1
    assert [decode(Image.open(io.BytesIO(f))) for f in files] == [[c] for c in BATCH]


def test_render_many_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renderer, "CODES_PER_PROCESS", 2)
    calls = 0
    real_run = subprocess.run

    def spy(args: list[str], **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    files = render_many(EAN13, BATCH, OutputFormat.EPS, RenderOptions())
    next(files)

    assert calls == 1


def test_invalid_code_in_batch_fails_the_call() -> None:
    with pytest.raises(RenderError, match="BWIPP ERROR"):
        list(render_many(EAN13, ["7861234567898", "123"], OutputFormat.PNG, RenderOptions()))


# ---------- Output splitting ----------


def test_split_pngs_rejects_truncated_output() -> None:
    valid = render(EAN13, CODE, OutputFormat.PNG, RenderOptions())

    assert renderer._split_pngs(valid + valid) == [valid, valid]
    with pytest.raises(RenderError, match="truncado"):
        renderer._split_pngs(valid[:-20])
    with pytest.raises(RenderError, match="inesperada"):
        renderer._split_pngs(b"not a png")


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (b"%!PS-Adobe-3.0\n%%EndComments\n", "Estructura inesperada"),
        (b"%!PS\n%%BeginProlog\n%%EndProlog\n%%Trailer\n", "Cabecera inesperada"),
        (b"%!PS-Adobe-3.0\n%%BeginProlog\n%%EndProlog\n%%Trailer\n", "Prolog inesperado"),
    ],
)
def test_split_ps_document_rejects_unexpected_structure(document: bytes, message: str) -> None:
    with pytest.raises(RenderError, match=message):
        renderer._split_ps_document(document, 1)
