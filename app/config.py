"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings populated from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SECRET_KEY: str
    BASE_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str
    FERNET_KEY: str

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    BOOTSTRAP_ADMIN_EMAIL: str
    BOOTSTRAP_ADMIN_PASSWORD: str

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
