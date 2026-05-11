"""Fernet symmetric encryption for stored Google API credentials."""
from cryptography.fernet import Fernet

from app.config import get_settings


_settings = get_settings()
_fernet = Fernet(_settings.FERNET_KEY.encode() if isinstance(_settings.FERNET_KEY, str) else _settings.FERNET_KEY)


def encrypt(plaintext: str) -> bytes:
    """Encrypt a string with the application-wide Fernet key."""
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    """Decrypt previously encrypted bytes back to a string."""
    return _fernet.decrypt(token).decode("utf-8")
