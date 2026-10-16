import json
import logging
import shutil

import pytest
from fastapi.testclient import TestClient

from app.api.routes import barcodes
from app.core.logging import JsonFormatter, configure_logging
from app.main import app
from app.services.renderer import RenderError

client = TestClient(app, raise_server_exceptions=False)
CODE = "7861234567898"


def formatted(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    formatter = JsonFormatter()
    return [json.loads(formatter.format(record)) for record in caplog.records]


def test_formatter_emits_json_with_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"name": "app.test", "levelname": "INFO", "msg": "hola %s", "args": ("mundo",)}
    )
    record.endpoint = "/health"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hola mundo"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["endpoint"] == "/health"
    assert payload["ts"].endswith("+00:00")


def test_each_request_is_logged_with_route_template(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.post("/api/v1/barcodes/ean13/validate", json={"code": CODE})

    (entry,) = [e for e in formatted(caplog) if e["logger"] == "app.request"]
    assert entry["message"] == "request"
    assert entry["method"] == "POST"
    assert entry["endpoint"] == "/api/v1/barcodes/{symbology}/validate"
    assert entry["status"] == 200
    assert isinstance(entry["duration_ms"], float)


def test_unmatched_routes_do_not_log_raw_path(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get(f"/{CODE}")

    (entry,) = [e for e in formatted(caplog) if e["logger"] == "app.request"]
    assert entry["endpoint"] == "unmatched"
    assert entry["status"] == 404


@pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript no instalado")
def test_codes_never_appear_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        client.post("/api/v1/barcodes/ean13/validate", json={"code": "786123456789"})
        client.post("/api/v1/barcodes/ean13/validate", json={"code": "7861234567897"})
        client.post(
            "/api/v1/barcodes/ean13/render?inline=true", json={"code": CODE, "format": "png"}
        )

    output = "\n".join(json.dumps(entry) for entry in formatted(caplog))
    assert "786123456789" not in output
    assert CODE.encode().hex() not in output


def test_render_failure_logs_without_ghostscript_output(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = CODE.encode().hex()

    def broken_render(*_: object) -> bytes:
        raise RenderError(f"Error: /typecheck in --cvn-- Operand stack: <{secret}>")

    monkeypatch.setattr(barcodes, "render", broken_render)

    with caplog.at_level(logging.ERROR):
        client.post("/api/v1/barcodes/ean13/render", json={"code": CODE, "format": "png"})

    entries = formatted(caplog)
    assert any(e["message"] == "render_failed" and e["format"] == "png" for e in entries)
    assert secret not in json.dumps(entries)


def test_configure_logging_routes_everything_through_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = logging.getLogger()
    access = logging.getLogger("uvicorn.access")
    monkeypatch.setattr(root, "handlers", list(root.handlers))
    monkeypatch.setattr(root, "level", root.level)
    monkeypatch.setattr(access, "propagate", access.propagate)

    configure_logging("warning")

    (handler,) = root.handlers
    assert isinstance(handler.formatter, JsonFormatter)
    assert root.level == logging.WARNING
    assert access.propagate is False  # replaced by the request log
    assert logging.getLogger("uvicorn.error").propagate is True
