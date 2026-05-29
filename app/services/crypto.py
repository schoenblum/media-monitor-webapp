"""Fernet symmetric encryption for stored Google API credentials.

Uses ``MultiFernet`` so credentials can survive a key rotation: ``FERNET_KEY``
is the primary key (all new ciphertext is encrypted with it), and any older
keys listed in ``FERNET_KEYS`` (comma-separated) are still accepted for
*decryption*. To rotate: generate a new key, set it as ``FERNET_KEY``, move the
previous value into ``FERNET_KEYS``, restart, then (optionally) re-encrypt
existing rows so the old key can eventually be dropped. See HANDOVER §7.3.
"""
from cryptography.fernet import Fernet, MultiFernet

from app.config import get_settings


_settings = get_settings()


def _build_fernet() -> MultiFernet:
    raw_keys = [_settings.FERNET_KEY]
    if _settings.FERNET_KEYS:
        raw_keys += [k.strip() for k in _settings.FERNET_KEYS.split(",") if k.strip()]
    return MultiFernet(
        [Fernet(k.encode() if isinstance(k, str) else k) for k in raw_keys]
    )


_fernet = _build_fernet()


def encrypt(plaintext: str) -> bytes:
    """Encrypt a string with the primary Fernet key."""
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    """Decrypt previously encrypted bytes (trying every configured key)."""
    return _fernet.decrypt(token).decode("utf-8")


def rotate_token(token: bytes) -> bytes:
    """Re-encrypt an existing token under the primary key.

    Used by a one-off re-encryption pass after a key rotation so the older
    keys in ``FERNET_KEYS`` can be retired. Decrypts with any configured key,
    re-encrypts with the primary.
    """
    return _fernet.rotate(token)
