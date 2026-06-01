"""Admin database backup (v2.6).

A weekly scheduler job (and an on-demand admin trigger) runs ``pg_dump`` over
the whole database, encrypts the dump at rest with a key derived from
``BACKUP_PASSPHRASE``, and writes it to ``BACKUP_DOWNLOAD_DIR``. Admins see a
"backup ready" card on the Dashboard and download the encrypted file over
HTTPS; on download it (and older prepared files) are pruned.

Why operator-encrypted rather than per-user: the live database stores results
and configs in plaintext, readable by anyone with server/DB access. Encrypting
the *backup* per-user would be inconsistent with that and would imply a privacy
guarantee the architecture can't make (scheduled runs write results with no
user present, so there is no password to encrypt with). A single operator
passphrase protects the downloaded artifact at rest to exactly the level the
operator already has — no more, no less — and keeps the backup restorable.

File format (``*.dump.enc``):
    b"MMBK1\\n" (6) || salt (16) || nonce (12) || AES-256-GCM ciphertext
Key = Scrypt(passphrase, salt, n=2**14, r=8, p=1, len=32); the magic is the
GCM associated data. Decrypt with ``ops/decrypt_backup.py`` then ``pg_restore``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from app.config import get_settings
from app.database import SessionLocal, engine


logger = logging.getLogger(__name__)

MAGIC = b"MMBK1\n"
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
# Fixed advisory-lock key so only one worker prepares a backup at a time.
_BACKUP_LOCK_KEY = 0x6D6D_4201  # "mm" + marker, within 31-bit range


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, passphrase: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext, MAGIC)
    return MAGIC + salt + nonce + ct


def decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    if blob[: len(MAGIC)] != MAGIC:
        raise ValueError("Not a Media Monitor backup file (bad magic header).")
    body = blob[len(MAGIC):]
    salt, nonce, ct = body[:16], body[16:28], body[28:]
    key = _derive_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ct, MAGIC)


# ---------------------------------------------------------------------------
# Prepared-file bookkeeping
# ---------------------------------------------------------------------------


def _download_dir() -> Path:
    return Path(get_settings().BACKUP_DOWNLOAD_DIR)


def _list_backups() -> list[Path]:
    d = _download_dir()
    if not d.exists():
        return []
    return sorted(d.glob("media_monitor_*.dump.enc"), key=lambda p: p.stat().st_mtime, reverse=True)


def latest_backup_info() -> dict | None:
    files = _list_backups()
    if not files:
        return None
    f = files[0]
    st = f.stat()
    return {
        "filename": f.name,
        "size_bytes": st.st_size,
        "created_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
    }


def latest_backup_path() -> Path | None:
    files = _list_backups()
    return files[0] if files else None


def prune_all_prepared() -> int:
    """Delete every prepared backup file. Used after a successful download."""
    n = 0
    for f in _list_backups():
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n


def _prune_keep(keep: int) -> None:
    for f in _list_backups()[keep:]:
        try:
            f.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Preparation (pg_dump → encrypt → write)
# ---------------------------------------------------------------------------


def _pg_dump_bin() -> str:
    """Resolve the pg_dump binary (systemd's PATH can be minimal)."""
    import shutil

    for cand in (shutil.which("pg_dump"), "/usr/bin/pg_dump", "/usr/local/bin/pg_dump"):
        if cand and Path(cand).exists():
            return cand
    return "pg_dump"


async def _pg_dump() -> bytes:
    """Run pg_dump -Fc against the configured database and return the bytes."""
    url = make_url(get_settings().DATABASE_URL)
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    args = [
        _pg_dump_bin(),
        "-h", url.host or "localhost",
        "-p", str(url.port or 5432),
        "-U", url.username or "postgres",
        "-d", url.database or "",
        "-Fc",
    ]
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {err.decode(errors='replace')[:500]}")
    return out


async def prepare_backup() -> dict:
    """Create one encrypted backup. Returns a status dict; never raises.

    Single-fires across the two workers via a fixed advisory lock. Skips with a
    clear reason when the passphrase is unset, the backend isn't Postgres, or
    pg_dump fails — so the admin UI can show *why* there's no backup.
    """
    settings = get_settings()
    if not settings.BACKUP_PASSPHRASE:
        logger.warning("Backup skipped: BACKUP_PASSPHRASE not configured")
        return {"ok": False, "reason": "BACKUP_PASSPHRASE not configured on the server."}
    if engine.dialect.name != "postgresql":
        return {"ok": False, "reason": "Backups require PostgreSQL."}

    async with SessionLocal() as db:
        got = (
            await db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _BACKUP_LOCK_KEY})
        ).scalar()
        if not got:
            logger.info("Backup: another worker is preparing one — skipping")
            return {"ok": False, "reason": "Another worker is already preparing a backup."}
        try:
            try:
                dump = await _pg_dump()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Backup pg_dump failed")
                return {"ok": False, "reason": f"pg_dump failed: {exc}"}

            blob = encrypt_bytes(dump, settings.BACKUP_PASSPHRASE)
            d = _download_dir()
            d.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = d / f"media_monitor_{ts}.dump.enc"
            tmp = path.with_suffix(".enc.tmp")
            tmp.write_bytes(blob)
            tmp.replace(path)
            _prune_keep(settings.BACKUP_KEEP)
            logger.info("Backup prepared: %s (%d bytes encrypted)", path.name, len(blob))
            return {
                "ok": True,
                "filename": path.name,
                "size_bytes": len(blob),
                "plain_bytes": len(dump),
            }
        finally:
            await db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _BACKUP_LOCK_KEY})
            await db.commit()


async def prepare_backup_and_notify() -> None:
    """Scheduler entry point: prepare a backup, then email admins if it worked."""
    result = await prepare_backup()
    if not result.get("ok"):
        return
    # Best-effort admin notification.
    try:
        from sqlalchemy import select

        from app.models.user import User, UserRole
        from app.services.email import send_backup_ready_email

        async with SessionLocal() as db:
            admins = (
                await db.execute(
                    select(User.email).where(User.role == UserRole.admin, User.is_active.is_(True))
                )
            ).scalars().all()
        for email in admins:
            await send_backup_ready_email(email, result["filename"], result["size_bytes"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Backup-ready notification failed: %s", exc)
