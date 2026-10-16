from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    # NoDecode: read the env var as a plain comma-separated string instead of JSON.
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    max_upload_mb: int = 2
    max_batch_rows: int = 500
    rate_limit_single: str = "60/minute"
    rate_limit_batch: str = "5/minute"
    ghostscript_timeout_seconds: float = 20
    log_level: str = "INFO"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _no_wildcard_origin_in_production(self) -> "Settings":
        if self.app_env == "production" and "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS no puede ser '*' en producción (RNF-09)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
