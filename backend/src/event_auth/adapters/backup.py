"""Versioned, authenticated, passphrase-encrypted pilot recovery archive."""

import io
import os
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"EVENTAUTH-BACKUP-1\x00"
MAX_BYTES = 256 * 1024 * 1024
FILES = frozenset(
    {
        "database.dump",
        "storage.key",
        "signing.key",
        "config.json",
        "manifest.json",
        "models.json",
        "thresholds.json",
    }
)


def derive(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 12:
        raise ValueError("Use a backup passphrase of at least 12 characters")
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(passphrase.encode())


def seal(files: dict[str, bytes], passphrase: str) -> bytes:
    if set(files) != FILES or sum(map(len, files.values())) > MAX_BYTES - 65536:
        raise ValueError("Invalid or oversized recovery bundle")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + salt + nonce
    return header + AESGCM(derive(passphrase, salt)).encrypt(nonce, output.getvalue(), header)


def unseal(data: bytes, passphrase: str) -> dict[str, bytes]:
    size = len(MAGIC) + 28
    if not data.startswith(MAGIC) or not size + 16 < len(data) <= MAX_BYTES:
        raise ValueError("Invalid or oversized backup")
    header, salt, nonce = data[:size], data[len(MAGIC) : len(MAGIC) + 16], data[size - 12 : size]
    try:
        raw = AESGCM(derive(passphrase, salt)).decrypt(nonce, data[size:], header)
    except InvalidTag:
        raise ValueError("Wrong passphrase or damaged backup") from None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != len(FILES) or {e.filename for e in entries} != FILES:
                raise ValueError("Unexpected backup contents")
            if any(e.compress_type != zipfile.ZIP_STORED for e in entries):
                raise ValueError("Unsupported archive compression")
            if sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError("Oversized backup contents")
            return {name: archive.read(name) for name in FILES}
    except (zipfile.BadZipFile, RuntimeError):
        raise ValueError("Damaged backup contents") from None


def write_private(path: Path, data: bytes) -> None:
    """Exclusive creation: do not overwrite a backup, key or symlink."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
