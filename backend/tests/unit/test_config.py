import pytest

from app.core.config import Settings


def test_allowed_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173, https://app.vercel.app")

    settings = Settings(_env_file=None)

    assert settings.allowed_origins == ["http://localhost:5173", "https://app.vercel.app"]


def test_defaults_match_plan() -> None:
    settings = Settings(_env_file=None)

    assert settings.max_upload_mb == 2
    assert settings.max_batch_rows == 500
    assert settings.ghostscript_timeout_seconds == 20
