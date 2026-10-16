import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app

client = TestClient(app)
ALLOWED_ORIGIN = "http://localhost:5173"


# ---------- CORS (RNF-09) ----------


def test_cors_preflight_from_allowed_origin() -> None:
    response = client.options(
        "/api/v1/barcodes/ean13/render",
        headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_rejects_other_origins() -> None:
    response = client.options(
        "/api/v1/barcodes/ean13/render",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_exposes_content_disposition_for_downloads() -> None:
    response = client.get("/api/v1/symbologies", headers={"Origin": ALLOWED_ORIGIN})

    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-expose-headers"] == "Content-Disposition"


def test_wildcard_origin_is_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")

    with pytest.raises(ValidationError, match="RNF-09"):
        Settings(_env_file=None)


# ---------- Rate limiting (RNF-10) ----------


def test_exceeding_rate_limit_returns_429_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_single", "2/minute")
    payload = {"code": "786123456789"}

    statuses = [
        client.post("/api/v1/barcodes/ean13/validate", json=payload).status_code for _ in range(2)
    ]
    response = client.post("/api/v1/barcodes/ean13/validate", json=payload)

    assert statuses == [200, 200]
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {
        "error": {
            "code": "RATE_LIMITED",
            "message": "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
            "details": {"retry_after_seconds": 60},
        }
    }


def test_rate_limit_is_per_client_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_single", "1/minute")
    payload = {"code": "786123456789"}
    first = TestClient(app, client=("203.0.113.1", 50000))
    second = TestClient(app, client=("203.0.113.2", 50000))

    assert first.post("/api/v1/barcodes/ean13/validate", json=payload).status_code == 200
    assert first.post("/api/v1/barcodes/ean13/validate", json=payload).status_code == 429
    assert second.post("/api/v1/barcodes/ean13/validate", json=payload).status_code == 200


# ---------- Request size (memory) ----------


def test_oversized_json_body_is_rejected_before_parsing() -> None:
    huge = '{"code": "' + "9" * (70 * 1024) + '", "format": "png"}'

    response = client.post(
        "/api/v1/barcodes/ean13/render",
        content=huge,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"] == {
        "code": "INVALID_REQUEST",
        "message": "La solicitud es demasiado grande.",
        "details": {},
    }


def test_normal_json_bodies_are_accepted() -> None:
    response = client.post("/api/v1/barcodes/ean13/validate", json={"code": "786123456789"})

    assert response.status_code == 200


# ---------- Security headers ----------


def test_api_responses_carry_security_headers() -> None:
    response = client.get("/api/v1/symbologies")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )


def test_error_responses_carry_security_headers_too() -> None:
    response = client.get("/no-existe")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"


def test_swagger_docs_are_not_blocked_by_the_api_csp() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
