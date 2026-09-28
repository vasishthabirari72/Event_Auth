import base64
import json
import shutil
import subprocess

import cv2
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from event_auth.adapters.pdf import PdfOutput
from event_auth.adapters.qr import decode_qr
from event_auth.adapters.signing import load_signer, sign
from event_auth.core.documents import CouponDocument


def test_signed_pdf_qr_round_trip(tmp_path):
    if not shutil.which("pdftoppm"):
        pytest.skip("PDF rasterizer unavailable")
    key = Ed25519PrivateKey.generate()
    payload = {
        "c": "TEST-COUPON",
        "e": "00000000-0000-4000-8000-000000000001",
        "s": "00000000-0000-4000-8000-000000000002",
        "o": "00000000-0000-4000-8000-000000000003",
        "m": "TEST-MEMBER",
        "t": 1790500000,
    }
    qr = sign(key, payload)
    document = CouponDocument(
        "Test Organization",
        "Test Event",
        "Test Slot",
        "TEST OPTION",
        "Test Member",
        "TEST-MEMBER",
        "TEST-COUPON",
        "2026-09-27",
        qr,
    )
    path = tmp_path / "coupon.pdf"
    path.write_bytes(PdfOutput().render(document))
    subprocess.run(
        [
            "pdftoppm",
            "-scale-to",
            "1800",
            "-singlefile",
            "-png",
            str(path),
            str(tmp_path / "coupon"),
        ],
        check=True,
        capture_output=True,
    )
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(tmp_path / "coupon.png")))
    assert decoded == qr
    assert decode_qr(base64.b64encode((tmp_path / "coupon.png").read_bytes()).decode()) == qr
    _, body, signature = decoded.split(".")
    raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    sig = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    assert json.loads(raw) == payload
    key.public_key().verify(sig, raw)
    with pytest.raises(InvalidSignature):
        key.public_key().verify(sig, raw + b"tamper")


def test_private_signing_key_permissions_and_reload(tmp_path):
    path = tmp_path / "signing.key"
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes_raw())
    path.chmod(0o600)
    first = sign(load_signer(path), {"c": "TEST"})
    assert sign(load_signer(path), {"c": "TEST"}) == first
    path.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        load_signer(path)
    link = tmp_path / "link.key"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="regular"):
        load_signer(link)
