import io
import shutil

import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import barcodes
from app.main import app
from app.services.renderer import RenderError

client = TestClient(app, raise_server_exceptions=False)
needs_gs = pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript no instalado")


def assert_error(response_json: dict[str, object], code: str) -> dict[str, object]:
    assert set(response_json) == {"error"}
    error = response_json["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == code
    return error


# ---------- /symbologies ----------


def test_list_symbologies() -> None:
    response = client.get("/api/v1/symbologies")

    assert response.status_code == 200
    assert response.json() == [{"id": "ean13", "name": "EAN-13", "formats": ["eps", "png"]}]


# ---------- /validate ----------


def test_validate_twelve_digits_returns_full_code() -> None:
    response = client.post("/api/v1/barcodes/ean13/validate", json={"code": "786-1234-56789"})

    assert response.status_code == 200
    assert response.json() == {"valid": True, "normalized": "7861234567898", "check_digit": 8}


def test_validate_wrong_check_digit_reports_expected_digit() -> None:
    response = client.post("/api/v1/barcodes/ean13/validate", json={"code": "7861234567897"})

    assert response.status_code == 422
    error = assert_error(response.json(), "INVALID_CHECK_DIGIT")
    assert error["message"] == "El dígito de control debe ser 8."
    assert error["details"] == {"expected": 8, "received": 7}


@pytest.mark.parametrize(
    ("code", "error_code"),
    [("78612345678A", "INVALID_CHARACTERS"), ("12345", "INVALID_LENGTH")],
)
def test_validate_invalid_input(code: str, error_code: str) -> None:
    response = client.post("/api/v1/barcodes/ean13/validate", json={"code": code})

    assert response.status_code == 422
    assert_error(response.json(), error_code)


def test_unknown_symbology_returns_404() -> None:
    response = client.post("/api/v1/barcodes/qrcode/validate", json={"code": "123"})

    assert response.status_code == 404
    error = assert_error(response.json(), "UNSUPPORTED_SYMBOLOGY")
    assert error["details"] == {"supported": ["ean13"]}


def test_request_validation_error_uses_error_format_without_echoing_input() -> None:
    response = client.post("/api/v1/barcodes/ean13/validate", json={"code": "9" * 65})

    assert response.status_code == 422
    error = assert_error(response.json(), "INVALID_REQUEST")
    assert error["details"] == {
        "fields": [{"field": "body.code", "message": "String should have at most 64 characters"}]
    }
    assert "9" * 65 not in response.text


def test_unknown_route_uses_error_format() -> None:
    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert_error(response.json(), "NOT_FOUND")


# ---------- /render ----------


@needs_gs
def test_render_png_attachment_decodes() -> None:
    response = client.post(
        "/api/v1/barcodes/ean13/render", json={"code": "786123456789", "format": "png"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'attachment; filename="7861234567898.png"'
    results = zxingcpp.read_barcodes(Image.open(io.BytesIO(response.content)))
    assert [r.text for r in results] == ["7861234567898"]


@needs_gs
def test_render_eps_inline_for_preview() -> None:
    response = client.post(
        "/api/v1/barcodes/ean13/render?inline=true",
        json={"code": "7861234567898", "format": "eps", "options": {"background": "transparent"}},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/postscript"
    assert response.headers["content-disposition"] == 'inline; filename="7861234567898.eps"'
    assert response.content.startswith(b"%!PS-Adobe-3.0 EPSF-3.0")


@needs_gs
def test_render_applies_options() -> None:
    response = client.post(
        "/api/v1/barcodes/ean13/render",
        json={
            "code": "7861234567898",
            "format": "png",
            "options": {"dpi": 600, "bar_color": "#1f3a93", "background": "transparent"},
        },
    )

    image = Image.open(io.BytesIO(response.content))
    assert image.mode == "RGBA"
    assert image.info["dpi"] == pytest.approx((600, 600), abs=0.05)


def test_render_rejects_invalid_code_before_rendering() -> None:
    response = client.post(
        "/api/v1/barcodes/ean13/render", json={"code": "7861234567897", "format": "png"}
    )

    assert response.status_code == 422
    assert_error(response.json(), "INVALID_CHECK_DIGIT")


@pytest.mark.parametrize(
    ("options", "field"),
    [
        ({"scale": 6}, "body.options.scale"),
        ({"scale": 0}, "body.options.scale"),
        ({"bar_height_mm": 9.9}, "body.options.bar_height_mm"),
        ({"dpi": 72}, "body.options.dpi"),
        ({"bar_color": "red"}, "body.options.bar_color"),
        ({"background": "#FFF"}, "body.options.background"),
        ({"background": "none"}, "body.options.background"),
        ({"background": "TRANSPARENT"}, "body.options.background"),
        ({"unknown": 1}, "body.options.unknown"),
    ],
)
def test_render_rejects_out_of_range_options(options: dict[str, object], field: str) -> None:
    response = client.post(
        "/api/v1/barcodes/ean13/render",
        json={"code": "7861234567898", "format": "png", "options": options},
    )

    assert response.status_code == 422
    error = assert_error(response.json(), "INVALID_REQUEST")
    details = error["details"]
    assert isinstance(details, dict)
    assert field in [f["field"] for f in details["fields"]]


def test_render_rejects_unknown_format() -> None:
    response = client.post(
        "/api/v1/barcodes/ean13/render", json={"code": "7861234567898", "format": "svg"}
    )

    assert response.status_code == 422
    assert_error(response.json(), "INVALID_REQUEST")


def test_render_failure_returns_render_failed_without_internals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_render(*_: object) -> bytes:
        raise RenderError("GPL Ghostscript: /undefined in --nostringval-- at /tmp/secret")

    monkeypatch.setattr(barcodes, "render", broken_render)

    response = client.post(
        "/api/v1/barcodes/ean13/render", json={"code": "7861234567898", "format": "png"}
    )

    assert response.status_code == 500
    assert_error(response.json(), "RENDER_FAILED")
    assert "Ghostscript" not in response.text


def test_unexpected_error_returns_internal_error_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_: object) -> bytes:
        raise RuntimeError("boom at /app/secret.py line 42")

    monkeypatch.setattr(barcodes, "render", explode)

    response = client.post(
        "/api/v1/barcodes/ean13/render", json={"code": "7861234567898", "format": "png"}
    )

    assert response.status_code == 500
    assert_error(response.json(), "INTERNAL_ERROR")
    assert "boom" not in response.text


def test_openapi_documents_all_endpoints() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {
        "/health",
        "/api/v1/symbologies",
        "/api/v1/barcodes/{symbology}/validate",
        "/api/v1/barcodes/{symbology}/render",
    } <= set(paths)


@pytest.mark.parametrize(
    ("background", "expected"),
    [("transparent", "transparent"), ("#fff8dc", "#FFF8DC")],
)
def test_background_is_normalized(background: str, expected: str) -> None:
    from app.schemas.barcodes import RenderOptionsIn

    assert RenderOptionsIn(background=background).to_domain().background == expected
