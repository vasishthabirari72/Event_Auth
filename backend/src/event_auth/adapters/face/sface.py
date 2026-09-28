from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from event_auth.core.face.matching import normalize


@dataclass(frozen=True)
class Quality:
    minimum_size: int = 80
    # Provisional webcam cutoff; consented population validation is still pending.
    # The reported clear-enough webcam frame scores 41.22 on its original crop.
    minimum_blur: float = 40.0
    minimum_brightness: float = 40.0
    maximum_brightness: float = 220.0
    maximum_eye_tilt: float = 0.25
    maximum_nose_offset: float = 0.35


class CaptureRejected(ValueError):
    pass


class SFaceEngine:
    """CPU ONNX inference. Models are provisioned separately; never downloaded here."""

    def __init__(self, detector: Path, recognizer: Path, quality: Quality | None = None) -> None:
        if not detector.is_file() or not recognizer.is_file():
            raise FileNotFoundError("Provision the approved local model files first")
        self.quality = quality or Quality()
        self.detector = cv2.FaceDetectorYN.create(str(detector), "", (320, 320), 0.9)
        self.recognizer = cv2.FaceRecognizerSF.create(str(recognizer), "")

    def _detect(self, frame: np.ndarray) -> np.ndarray | None:
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)
        # YuNet's trained face-size range is about 10–300 pixels. A close-up can
        # exceed that range; retry smaller, then restore all geometry for SFace.
        for target in (320, 240):
            if faces is not None and len(faces) > 0:
                break
            if max(width, height) <= target:
                continue
            scale = target / max(width, height)
            small_width, small_height = round(width * scale), round(height * scale)
            small = cv2.resize(frame, (small_width, small_height), interpolation=cv2.INTER_AREA)
            self.detector.setInputSize((small_width, small_height))
            _, faces = self.detector.detect(small)
            if faces is not None:
                faces = faces.copy()
                faces[:, [0, 2, 4, 6, 8, 10, 12]] *= width / small_width
                faces[:, [1, 3, 5, 7, 9, 11, 13]] *= height / small_height
        return faces

    def embed(self, image: bytes) -> tuple[float, ...]:
        frame = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise CaptureRejected("Unreadable image")
        height, width = frame.shape[:2]
        if width > 1920 or height > 1920:
            raise CaptureRejected("Use a camera frame no larger than 1920 pixels")
        faces = self._detect(frame)
        if faces is None or len(faces) == 0:
            raise CaptureRejected("No face detected")
        if len(faces) > 1:
            raise CaptureRejected("One person at a time; look at the camera")
        face = faces[0]
        x, y, w, h = (int(value) for value in face[:4])
        if min(w, h) < self.quality.minimum_size:
            raise CaptureRejected("Move closer")
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise CaptureRejected("Keep your whole face inside the camera view")
        crop = frame[y : y + h, x : x + w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        if not self.quality.minimum_brightness <= brightness <= self.quality.maximum_brightness:
            raise CaptureRejected("Adjust the lighting")
        if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < self.quality.minimum_blur:
            raise CaptureRejected("Hold still")
        right_eye, left_eye, nose = face[4:6], face[6:8], face[8:10]
        eye_span = float(np.linalg.norm(left_eye - right_eye))
        if eye_span <= 0:
            raise CaptureRejected("Look straight at the camera")
        tilt = abs(float(left_eye[1] - right_eye[1])) / eye_span
        nose_offset = abs(float(nose[0] - (left_eye[0] + right_eye[0]) / 2)) / eye_span
        if tilt > self.quality.maximum_eye_tilt or nose_offset > self.quality.maximum_nose_offset:
            raise CaptureRejected("Look straight at the camera")
        aligned = self.recognizer.alignCrop(frame, face)
        feature = self.recognizer.feature(aligned).reshape(-1)
        return normalize(tuple(float(value) for value in feature))

    def thumbnail(self, image: bytes) -> bytes:
        # Reuse the validated single-face detection; retain only a small cropped reference.
        self.embed(image)
        frame = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise CaptureRejected("Unreadable image")
        faces = self._detect(frame)
        if faces is None or len(faces) != 1:
            raise CaptureRejected("Unreadable image")
        x, y, w, h = (int(value) for value in faces[0][:4])
        crop = frame[y : y + h, x : x + w]
        scale = 160 / max(w, h)
        small = cv2.resize(crop, (max(1, int(w * scale)), max(1, int(h * scale))))
        ok, encoded = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            raise CaptureRejected("Unreadable image")
        return encoded.tobytes()
