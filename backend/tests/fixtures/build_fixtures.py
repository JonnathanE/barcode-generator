"""Build the .xlsx fixtures for the batch flow (Phase 5, task 6).

    uv run python -m tests.fixtures.build_fixtures

The generated files are committed: the frontend (Phase 6) uses them too.
"""

import io
import zipfile
from collections.abc import Sequence
from pathlib import Path

from openpyxl import Workbook

from app.domain.ean13 import compute_check_digit

HERE = Path(__file__).parent
SCIENTIFIC = "0.00E+00"
TEXT = "@"

Cell = str | int | float | None


def workbook(rows: Sequence[Sequence[Cell]], formats: dict[str, str] | None = None) -> bytes:
    book = Workbook()
    sheet = book.worksheets[0]
    sheet.title = "Códigos"
    for row in rows:
        sheet.append(list(row))
    for coordinate, number_format in (formats or {}).items():
        sheet[coordinate].number_format = number_format
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def ean13(body: str) -> str:
    return f"{body}{compute_check_digit(body)}"


def with_macros(xlsx: bytes) -> bytes:
    """Same workbook plus a VBA project and the macro-enabled content type."""
    source = zipfile.ZipFile(io.BytesIO(xlsx))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.replace(
                    b"spreadsheetml.sheet.main+xml",
                    b"sheet.macroEnabled.main+xml",
                )
            target.writestr(item, data)
        target.writestr("xl/vbaProject.bin", b"\xd0\xcf\x11\xe0 fake VBA project")
    return output.getvalue()


def zip_without_workbook() -> bytes:
    """A valid ZIP (like a .docx) renamed to .xlsx."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return output.getvalue()


FIXTURES: dict[str, bytes] = {
    # Text cells: 12 digits, 13 digits, separators.
    "validos.xlsx": workbook(
        [
            ["codigo", "nombre_archivo"],
            ["786123456789", "leche-entera"],
            ["9780306406157", None],
            ["400-6381-33393-1", "galletas"],
            ["590 1234 12345 7", None],
        ],
        {"A2": TEXT, "A3": TEXT, "A4": TEXT, "A5": TEXT},
    ),
    # Wrong characters, length and check digit; a row with a name but no code.
    "invalidos.xlsx": workbook(
        [
            ["codigo", "nombre_archivo"],
            ["78612345678A", None],
            ["12345", None],
            ["7861234567897", None],
            [None, "sin-codigo"],
            ["4006381333931", "valido"],
        ]
    ),
    # Numbers as Excel stores them: int, float, 11 digits that lost two leading zeros.
    "numericos.xlsx": workbook(
        [
            ["codigo"],
            [786123456789],
            [5901234123457],
            [4006381333931.0],
            [12345678905],  # was 0012345678905
            [123.5],
        ]
    ),
    # RF-11: scientific notation, as text (CSV import) and as formatted numbers.
    "cientifica.xlsx": workbook(
        [
            ["codigo"],
            ["7.86123E+12"],  # lost digits
            ["7.861234567898E+12"],  # complete
            [7861230000000],  # typed truncated, shown as 7.86E+12
            [7861234567898],  # full value, only displayed in scientific notation
        ],
        {"A4": SCIENTIFIC, "A5": SCIENTIFIC},
    ),
    # RF-17: the same code written three ways, plus a different one.
    "duplicados.xlsx": workbook(
        [
            ["ean13", "nombre"],
            ["7861234567898", "primero"],
            ["786123456789", "segundo"],
            ["786-1234-56789-8", "tercero"],
            ["4006381333931", "otro"],
        ]
    ),
    # RF-18: blank rows and whitespace-only cells are ignored.
    "filas_vacias.xlsx": workbook(
        [
            ["codigo", "nombre_archivo"],
            [None, None],
            ["7861234567898", None],
            ["   ", None],
            [None, None],
            [None, None],
            ["4006381333931", None],
        ]
    ),
    # RNF-12 / RF-16: path traversal, reserved names and collisions.
    "nombres_peligrosos.xlsx": workbook(
        [
            ["codigo", "nombre_archivo"],
            [ean13("786000000001"), "../../x"],
            [ean13("786000000002"), "..\\..\\windows\\system32"],
            [ean13("786000000003"), "CON"],
            [ean13("786000000004"), "a/b:c*d"],
            [ean13("786000000005"), "Leche"],
            [ean13("786000000006"), "leche"],
            [ean13("786000000007"), "..."],
            [ean13("786000000008"), "x" * 150],
        ]
    ),
    # Header not in the first row, with accents and different case (RF-10).
    "encabezado_con_titulo.xlsx": workbook(
        [
            ["Productos de la tienda"],
            [],
            ["Código", "Precio", "Nombre"],
            ["7861234567898", 1.25, "Leche"],
        ]
    ),
    "sin_columna_codigo.xlsx": workbook([["producto", "precio"], ["Leche", 1.25]]),
    "no_es_excel.xlsx": b"Esto es un archivo de texto renombrado a .xlsx\n",
    "zip_no_excel.xlsx": zip_without_workbook(),
    "con_macros.xlsx": with_macros(workbook([["codigo"], ["7861234567898"]])),
    # 500 valid codes, the default MAX_BATCH_ROWS: for measurements and the frontend.
    "lote_500.xlsx": workbook(
        [["codigo", "nombre_archivo"]]
        + [[ean13(f"786{i:09d}"), f"producto-{i:03d}"] for i in range(500)],
        {f"A{row}": TEXT for row in range(2, 502)},
    ),
}


def main() -> None:
    for name, content in FIXTURES.items():
        (HERE / name).write_bytes(content)
        print(f"{name}: {len(content):,} bytes")


if __name__ == "__main__":
    main()
