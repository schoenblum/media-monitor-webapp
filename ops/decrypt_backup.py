#!/usr/bin/env python3
"""Decrypt a Media Monitor encrypted database backup (*.dump.enc → *.dump).

The admin "Download backup" button on the Dashboard produces an encrypted file
(see app/services/backup.py). Decrypt it locally with the backup passphrase,
then restore with pg_restore. The server is never involved in decryption.

Usage:
    python3 ops/decrypt_backup.py media_monitor_YYYYMMDDTHHMMSSZ.dump.enc
    # writes media_monitor_YYYYMMDDTHHMMSSZ.dump (prompts for the passphrase)

    # then, against a fresh/empty database:
    pg_restore -h HOST -U media_monitor_user -d media_monitor \\
               --clean --if-exists media_monitor_YYYYMMDDTHHMMSSZ.dump

Only dependency: `cryptography` (pip install cryptography).
"""
import getpass
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"MMBK1\n"


def decrypt(blob: bytes, passphrase: str) -> bytes:
    if blob[: len(MAGIC)] != MAGIC:
        raise ValueError("Not a Media Monitor backup file (bad magic header).")
    body = blob[len(MAGIC):]
    salt, nonce, ct = body[:16], body[16:28], body[28:]
    key = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1).derive(passphrase.encode("utf-8"))
    return AESGCM(key).decrypt(nonce, ct, MAGIC)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    if not src.is_file():
        print(f"error: {src} not found", file=sys.stderr)
        return 1
    out = src.with_suffix("") if src.suffix == ".enc" else src.with_name(src.name + ".dump")
    passphrase = getpass.getpass("Backup passphrase: ")
    try:
        plaintext = decrypt(src.read_bytes(), passphrase)
    except Exception as exc:  # noqa: BLE001
        print(f"error: decryption failed ({exc}). Wrong passphrase or corrupt file.", file=sys.stderr)
        return 1
    out.write_bytes(plaintext)
    print(f"✓ wrote {out} ({len(plaintext)} bytes). Restore with pg_restore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
