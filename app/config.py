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
    # Optional comma-separated list of *older* Fernet keys, kept only so
    # credentials encrypted under a previous key stay readable during a key
    # rotation. New ciphertext always uses FERNET_KEY. See HANDOVER §7.3.
    FERNET_KEYS: Optional[str] = None

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_SSL: bool = False
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    BOOTSTRAP_ADMIN_EMAIL: str
    BOOTSTRAP_ADMIN_PASSWORD: str

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    # Admin database backup (v2.6). The weekly job pg_dumps the whole database,
    # encrypts it at rest with a key derived from BACKUP_PASSPHRASE, and makes
    # it downloadable to admins. Without a passphrase the feature reports
    # "not configured" rather than writing a plaintext dump. Decrypt with
    # ops/decrypt_backup.py, then pg_restore.
    BACKUP_PASSPHRASE: Optional[str] = None
    BACKUP_DOWNLOAD_DIR: str = "/var/backups/media_monitor/prepared"
    BACKUP_KEEP: int = 2  # prepared encrypted backups to retain on the server


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
