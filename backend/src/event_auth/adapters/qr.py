import base64

import cv2
import numpy as np

from event_auth.core.members.rules import RuleViolation


def decode_qr(encoded: str) -> str | None:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise RuleViolation("invalid_image") from error
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or max(frame.shape[:2]) > 1920:
        raise RuleViolation("invalid_image")
    value, _, _ = cv2.QRCodeDetector().detectAndDecode(frame)
    return str(value) if value and len(value) <= 2000 else None
