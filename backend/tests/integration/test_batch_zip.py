import csv
import io
import shutil
import sys
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import zxingcpp
from PIL import Image

from app.services.batch import build_zip, validate_batch
from app.services.excel_reader import read_sheet
from app.symbologies.base import OutputFormat, RenderOptions
from app.symbologies.registry import registry

pytestmark = pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript no instalado")

EAN13 = registry.get("ean13")
FIXTURES = Path(__file__).parent.parent / "fixtures"

# --- Detect any file opened for writing (RNF-07) -------------------------------------
_write_opens: list[str] | None = None


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if _write_opens is None or event != "open":
        return
    path, mode, flags = args
    if isinstance(path, int):
        return  # a file descriptor (e.g. the pipe to Ghostscript's stdin), not a file
    writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
        isinstance(flags, int) and flags & 0o3  # O_WRONLY | O_RDWR
    )
    if writes:
        _write_opens.append(str(path))


sys.addaudithook(_audit)  # audit hooks can't be removed; it's inert outside the context


@contextmanager
def no_disk_writes() -> Iterator[list[str]]:
    global _write_opens
    _write_opens = []
    try:
        yield _write_opens
    finally:
        _write_opens = None


def report_for(name: str) -> Any:
    rows = read_sheet(
        (FIXTURES / name).read_bytes(), max_rows=500, max_mb=2, restore_leading_zeros=False
    )
    return validate_batch(EAN13, rows)


def test_zip_has_png_eps_and_report_and_every_png_decodes() -> None:
    report = report_for("duplicados.xlsx")

    data = build_zip(EAN13, report, [OutputFormat.PNG, OutputFormat.EPS], RenderOptions())

    archive = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(archive.namelist()) == [
        "eps/otro.eps",
        "eps/primero.eps",
        "png/otro.png",
        "png/primero.png",
        "reporte.csv",
    ]
    expected = {"png/primero.png": "7861234567898", "png/otro.png": "4006381333931"}
    for name, code in expected.items():
        image = Image.open(io.BytesIO(archive.read(name)))
        assert [r.text for r in zxingcpp.read_barcodes(image)] == [code]
    for name in ("eps/primero.eps", "eps/otro.eps"):
        assert archive.read(name).startswith(b"%!PS-Adobe-3.0 EPSF-3.0")


def test_report_lists_every_row_including_duplicates() -> None:
    report = report_for("duplicados.xlsx")

    data = build_zip(EAN13, report, [OutputFormat.PNG], RenderOptions())

    text = zipfile.ZipFile(io.BytesIO(data)).read("reporte.csv").decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [(r["fila"], r["estado"]) for r in rows] == [
        ("2", "ok"),
        ("3", "duplicado"),
        ("4", "duplicado"),
        ("5", "ok"),
    ]
    assert rows[0]["archivo"] == "png/primero.png"


def test_only_requested_formats_and_valid_rows_are_generated() -> None:
    report = report_for("invalidos.xlsx")

    data = build_zip(EAN13, report, [OutputFormat.EPS], RenderOptions())

    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert names == ["eps/valido.eps", "reporte.csv"]


def test_dangerous_names_stay_inside_their_folder() -> None:
    report = report_for("nombres_peligrosos.xlsx")

    data = build_zip(EAN13, report, [OutputFormat.PNG], RenderOptions(scale=1))

    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    for name in names:
        assert ".." not in name and "\\" not in name and not name.startswith("/")
        assert name == "reporte.csv" or name.count("/") == 1
    assert "png/___x.png" in names
    assert "png/_CON.png" in names
    assert {"png/Leche.png", "png/leche_2.png"} <= set(names)
    assert all(len(Path(n).stem) <= 100 for n in names)


def test_png_is_stored_and_eps_is_compressed() -> None:
    report = report_for("validos.xlsx")

    data = build_zip(EAN13, report, [OutputFormat.PNG, OutputFormat.EPS], RenderOptions())

    infos = {i.filename: i for i in zipfile.ZipFile(io.BytesIO(data)).infolist()}
    assert infos["png/leche-entera.png"].compress_type == zipfile.ZIP_STORED
    assert infos["eps/leche-entera.eps"].compress_type == zipfile.ZIP_DEFLATED
    assert infos["eps/leche-entera.eps"].compress_size < infos["eps/leche-entera.eps"].file_size / 2


def test_reading_validating_and_zipping_never_write_to_disk() -> None:
    content = (FIXTURES / "validos.xlsx").read_bytes()

    with no_disk_writes() as writes:
        rows = read_sheet(content, max_rows=500, max_mb=2, restore_leading_zeros=False)
        report = validate_batch(EAN13, rows)
        build_zip(EAN13, report, [OutputFormat.PNG, OutputFormat.EPS], RenderOptions())

    assert writes == []


def test_the_disk_write_detector_works(tmp_path: Path) -> None:
    with no_disk_writes() as writes:
        (tmp_path / "x.txt").write_text("hola")

    assert writes == [str(tmp_path / "x.txt")]
