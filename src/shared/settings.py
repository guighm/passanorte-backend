"""Typed, explicit process settings; secret values never appear in errors."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr
from sqlalchemy.engine import make_url


class ConfigurationError(RuntimeError):
    pass


def secret(name: str, *, required: bool = True) -> str:
    value, filename = os.environ.get(name, ""), os.environ.get(f"{name}_FILE", "")
    if value and filename:
        raise ConfigurationError(f"Configure only {name} or {name}_FILE")
    if filename:
        try:
            value = Path(filename).read_text(encoding="utf-8").strip()
        except OSError:
            raise ConfigurationError(f"Cannot read {name}_FILE") from None
    if required and not value:
        raise ConfigurationError(f"Missing {name} or {name}_FILE")
    return value


class Settings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "production"
    database_url: SecretStr
    rabbitmq_url: SecretStr
    jwt_issuer: str = Field(default="passanorte", min_length=1)
    jwt_audience: str = Field(default="passanorte-api", min_length=1)
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)

    catalog_service_url: HttpUrl = HttpUrl("http://localhost:8002")
    deployment_city: str = Field(default="Manaus", min_length=1)
    deployment_timezone: str = "America/Manaus"
    deployment_language: str = "pt-BR"
    map_center_latitude: float = Field(default=-3.119, ge=-90, le=90)
    map_center_longitude: float = Field(default=-60.0217, ge=-180, le=180)
    edge_public_url: HttpUrl = HttpUrl("https://localhost:8443")
    llm_provider: Literal["stub", "ollama", "gemini"] = "stub"
    llm_ollama_url: HttpUrl = HttpUrl("http://localhost:11434")
    llm_ollama_model: str = Field(default="llama3.1", min_length=1)

    @classmethod
    def load(cls) -> Settings:
        settings = cls.model_validate({
            **{name: os.environ[name.upper()] for name in cls.model_fields if name.upper() in os.environ},
            "app_env": os.environ.get("APP_ENV", "production"),
            "database_url": secret("DATABASE_URL"),
            "rabbitmq_url": secret("RABBITMQ_URL", required=False),
            "jwt_issuer": os.environ.get("JWT_ISSUER", "passanorte"),
            "jwt_audience": os.environ.get("JWT_AUDIENCE", "passanorte-api"),
            "access_token_minutes": os.environ.get("ACCESS_TOKEN_MINUTES", "15"),
            "refresh_token_days": os.environ.get("REFRESH_TOKEN_DAYS", "7"),
        })
        try:
            url = make_url(settings.database_url.get_secret_value())
            if settings.app_env != "test" and url.drivername != "postgresql+psycopg":
                raise ValueError
        except Exception:
            raise ConfigurationError("DATABASE_URL must use postgresql+psycopg (SQLite only in test)") from None
        broker = settings.rabbitmq_url.get_secret_value()
        if settings.app_env != "test" and not broker.startswith(("amqp://", "amqps://")):
            raise ConfigurationError("RABBITMQ_URL is required and must use amqp(s)")
        try:
            ZoneInfo(settings.deployment_timezone)
        except ZoneInfoNotFoundError:
            if os.name != "nt" or settings.deployment_timezone != "America/Manaus":
                raise ConfigurationError("DEPLOYMENT_TIMEZONE must be an installed IANA time zone") from None
        return settings


def validate_service(service: str) -> Settings:
    from shared.security import encryption, signing_key, verification_keys

    settings = Settings.load()
    verification_keys()
    if settings.app_env != "test":
        if service in {"auth", "benefits", "catalog", "gamification"}:
            secret("INTERNAL_API_TOKEN")
        if service == "gamification" and not os.environ.get("CATALOG_SERVICE_URL"):
            raise ConfigurationError("Missing CATALOG_SERVICE_URL")
    if service == "chatbot" and settings.llm_provider == "gemini":
        secret("LLM_GEMINI_API_KEY")
    if service == "auth":
        signing_key()
        encryption()
        hmac_key = secret("PII_HMAC_KEY")
        if hmac_key in [key.strip() for key in secret("PII_ENCRYPTION_KEY").split(",")]:
            raise ConfigurationError("PII_HMAC_KEY must be independent from encryption keys")
        if len(hmac_key.encode()) < 32:
            raise ConfigurationError("PII_HMAC_KEY must have at least 32 bytes")
    return settings
