import base64
import json
import threading
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import delete, select

from event_auth.adapters.database.models import FaceTemplate
from event_auth.adapters.face.sface import CaptureRejected, SFaceEngine
from event_auth.core.face.contracts import FaceEngine, Template
from event_auth.core.face.matching import Thresholds, identify
from event_auth.core.members.rules import RuleViolation
from event_auth.services.admin import AdminService
from event_auth.services.auth import lock


class EnrollmentEngine(FaceEngine, Protocol):
    def thumbnail(self, image: bytes) -> bytes: ...


class Enrollment:
    def __init__(self, models: Path, engine: EnrollmentEngine | None = None) -> None:
        self.models, self.engine = models, engine
        config = json.loads((models / "thresholds.example.json").read_text())
        self.version = str(config["model_version"])
        self.thresholds = Thresholds(float(config["medium"]), float(config["high"]))
        self.mutex = threading.Lock()

    def runtime(self) -> EnrollmentEngine:
        if self.engine is None:
            from event_auth.face_lab import model_provenance

            model_provenance(self.models)
            self.engine = SFaceEngine(self.models / "yunet.onnx", self.models / "sface.onnx")
        return self.engine

    def decode(self, encoded: str) -> bytes:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise RuleViolation("invalid_image") from exc
        if len(raw) > 1_500_000:
            raise RuleViolation("invalid_image")
        return raw

    def check(self, service: AdminService, member_id: UUID, consent_id: UUID, frame: str) -> None:
        if not service.config.experimental_face:
            raise RuleViolation("face_disabled")
        service.require_consent(member_id, consent_id)
        with self.mutex:
            self.runtime().embed(self.decode(frame))

    def save(
        self,
        service: AdminService,
        member_id: UUID,
        consent_id: UUID,
        frames: list[str],
        reviewed: list[UUID],
    ) -> dict[str, Any]:
        if not service.config.experimental_face:
            raise RuleViolation("face_disabled")
        # Serialize enrollments across workers so simultaneous duplicates cannot bypass review.
        lock(service.db, "face_enrollment")
        member = service.require_consent(member_id, consent_id)
        if len(frames) != 3 or len(set(frames)) != 3:
            raise RuleViolation("three_distinct_frames")
        with self.mutex:
            engine = self.runtime()
            raw = [self.decode(frame) for frame in frames]
            vectors = [engine.embed(image) for image in raw]
            thumbnail = base64.b64encode(engine.thumbnail(raw[0])).decode()
        existing: dict[UUID, list[Template]] = {}
        for value in service.db.scalars(
            select(FaceTemplate).where(
                FaceTemplate.member_id != member_id, FaceTemplate.model_version == self.version
            )
        ):
            existing.setdefault(value.member_id, []).append(
                Template(
                    value.member_id, value.model_version, tuple(service.vault.open(value.embedding))
                )
            )
        duplicates = {
            candidate
            for candidate, templates in existing.items()
            if any(
                identify(vector, templates, {candidate}, self.version, self.thresholds).member_id
                for vector in vectors
            )
        }
        if duplicates != set(reviewed):
            return {
                "saved": False,
                "duplicates": [
                    service.member_view(service.member(candidate))
                    for candidate in sorted(duplicates)
                ],
                "experimental": True,
            }
        service.db.execute(delete(FaceTemplate).where(FaceTemplate.member_id == member_id))
        for vector in vectors:
            service.db.add(
                FaceTemplate(
                    member_id=member_id,
                    consent_id=consent_id,
                    model_version=self.version,
                    embedding=service.vault.seal(vector),
                )
            )
        member.thumbnail = service.vault.seal(thumbnail)
        member.revision += 1
        service.audit("face_enroll", member_id, [consent_id])
        if duplicates:
            service.audit("duplicate_override", member_id, list(duplicates))
        return {"saved": True, "duplicates": [], "experimental": True}


HINTS = {
    "No face detected": "no_face",
    "Move closer": "move_closer",
    "Hold still": "hold_still",
    "Adjust the lighting": "lighting",
    "Look straight at the camera": "look_straight",
    "One person at a time; look at the camera": "one_person",
    "Keep your whole face inside the camera view": "whole_face",
}


def capture_error(error: CaptureRejected) -> str:
    return HINTS.get(str(error), "invalid_image")
