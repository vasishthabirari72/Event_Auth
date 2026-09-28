import base64
import json
import stat
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def load_signer(path: Path) -> Ed25519PrivateKey:
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Signing key must be a regular private file")
    if path.stat().st_mode & 0o077:
        raise ValueError("Signing key permissions must be 0600")
    return Ed25519PrivateKey.from_private_bytes(path.read_bytes())


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def sign(key: Ed25519PrivateKey, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return "v1." + encoded(raw) + "." + encoded(key.sign(raw))


def verify(key: Ed25519PrivateKey, value: str) -> dict[str, Any]:
    from cryptography.exceptions import InvalidSignature

    try:
        version, body, signature = value.split(".")
        if version != "v1" or len(value) > 2000:
            raise ValueError("Invalid coupon")
        raw = base64.b64decode(body + "=" * (-len(body) % 4), altchars=b"-_", validate=True)
        sig = base64.b64decode(
            signature + "=" * (-len(signature) % 4), altchars=b"-_", validate=True
        )
        key.public_key().verify(sig, raw)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {"c", "e", "s", "o", "m", "t"}:
            raise ValueError("Invalid coupon")
        return payload
    except (ValueError, TypeError, InvalidSignature) as error:
        raise ValueError("Invalid coupon") from error


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Provision a private server signing key once")
    parser.add_argument("path", type=Path)
    path = parser.parse_args().path.expanduser().resolve()
    project = Path(__file__).resolve().parents[4]
    if path.is_relative_to(project):
        raise ValueError("Keep signing keys outside the project directory")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation never silently replaces keys for already-issued coupons.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(Ed25519PrivateKey.generate().private_bytes_raw())
    print("Signing key provisioned. Back it up with the database recovery keys.")


if __name__ == "__main__":
    main()
