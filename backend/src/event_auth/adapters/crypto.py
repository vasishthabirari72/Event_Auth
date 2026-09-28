import base64
import hashlib
import hmac
import json
import os
import stat
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from event_auth.core.members.rules import validate_pin


def pin_hash(pin: str) -> str:
    validate_pin(pin)
    salt = os.urandom(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def pin_matches(pin: str, encoded: str) -> bool:
    raw = base64.b64decode(encoded)
    digest = hashlib.scrypt(pin.encode(), salt=raw[:16], n=16384, r=8, p=1)
    return hmac.compare_digest(digest, raw[16:])


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Vault:
    def __init__(self, key: bytes) -> None:
        self.cipher = Fernet(key)

    @classmethod
    def from_file(cls, path: Path) -> "Vault":
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("Encryption key must be a regular private file")
        if path.stat().st_mode & 0o077:
            raise ValueError("Encryption key permissions must be 0600")
        return cls(path.read_bytes().strip())

    def seal(self, value: Any) -> bytes:
        return self.cipher.encrypt(json.dumps(value, allow_nan=False).encode())

    def open(self, value: bytes) -> Any:
        return json.loads(self.cipher.decrypt(value))
