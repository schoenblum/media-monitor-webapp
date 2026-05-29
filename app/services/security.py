"""Password hashing, JWT issuance/verification, webhook key generation."""
import hashlib
import hmac
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


# ---------------------------------------------------------------------------
# Webhook API keys — issued as "<key_id>.<secret>"
#
# The secret is a high-entropy random token, so a fast keyed hash (SHA-256) is
# appropriate and lets verification be a single indexed lookup on ``key_id``
# followed by one constant-time comparison — instead of a bcrypt verify against
# every user's stored hash (the old O(n) scan, which was also a DoS amplifier).
# ---------------------------------------------------------------------------


def generate_webhook_key() -> tuple[str, str, str]:
    """Return ``(full_key, key_id, secret_hash)`` for a new webhook key.

    ``full_key`` ("<key_id>.<secret>") is shown to the user exactly once;
    ``key_id`` and ``secret_hash`` are persisted.
    """
    key_id = secrets.token_hex(8)  # 16 hex chars, fits webhook_key_id(32)
    secret = secrets.token_urlsafe(32)
    return f"{key_id}.{secret}", key_id, hash_webhook_secret(secret)


def hash_webhook_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_webhook_secret(secret: str, secret_hash: str) -> bool:
    return hmac.compare_digest(hash_webhook_secret(secret), secret_hash)


def split_webhook_key(full_key: str) -> tuple[str, str] | None:
    """Split "<key_id>.<secret>" → (key_id, secret), or None if malformed."""
    if not full_key or "." not in full_key:
        return None
    key_id, _, secret = full_key.partition(".")
    if not key_id or not secret:
        return None
    return key_id, secret
