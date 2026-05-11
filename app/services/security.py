"""Password hashing, JWT issuance/verification, webhook key generation."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings


_settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def hash_token(token: str) -> str:
    """One-way hash for password-reset tokens and webhook keys (uses bcrypt)."""
    return _pwd.hash(token)


def verify_token(token: str, token_hash: str) -> bool:
    return _pwd.verify(token, token_hash)


def create_access_token(subject: str | UUID, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or _settings.JWT_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, _settings.SECRET_KEY, algorithm=_settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.JWT_ALGORITHM])
    except JWTError:
        return None


def generate_token(num_bytes: int = 32) -> str:
    """URL-safe random token for password resets and webhook API keys."""
    return secrets.token_urlsafe(num_bytes)
