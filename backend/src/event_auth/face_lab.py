"""Consented M1 webcam evaluation; only aggregate reports are persisted."""

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import cv2

from event_auth.adapters.face.sface import CaptureRejected, SFaceEngine
from event_auth.core.face.contracts import FaceEngine, Template
from event_auth.core.face.matching import Thresholds, identify
from event_auth.evaluation.benchmark import MODEL_VERSION, machine_info, write_report
from event_auth.evaluation.metrics import Trial, recommend, summarize

_MESSAGES = json.loads((Path(__file__).parent / "evaluation" / "en.json").read_text())


def message(key: str, **values: object) -> str:
    return str(_MESSAGES[key]).format(**values)


def consent(label: str) -> bool:
    return input(message("consent", label=label)).strip().lower() in {"adult", "guardian"}


@dataclass(frozen=True)
class Captured[T]:
    value: T
    seconds: float
    rejected: int


def capture[T](process: Callable[[bytes], T], camera_index: int) -> Captured[T]:
    camera = cv2.VideoCapture(camera_index)
    rejected = 0
    try:
        if not camera.isOpened():
            raise RuntimeError(message("camera_unavailable"))
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError(message("frame_unavailable"))
            cv2.imshow(message("window"), frame)
            key = cv2.waitKey(20) & 0xFF
            if key == 27:
                raise KeyboardInterrupt
            if key != 32:
                continue
            start = time.perf_counter()
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise RuntimeError(message("encoding_failed"))
            try:
                value = process(encoded.tobytes())
                return Captured(value, time.perf_counter() - start, rejected)
            except CaptureRejected as error:
                rejected += 1
                print(str(error))
    finally:
        camera.release()
        cv2.destroyAllWindows()


def collect(
    engine: FaceEngine,
    templates: list[Template],
    participants: list[UUID],
    camera_index: int,
    repeats: int,
    unknown_people: int,
) -> list[Trial]:
    candidates = set(participants)
    trials: list[Trial] = []

    def attempt(expected: UUID | None) -> Trial:
        def process(image: bytes) -> tuple[tuple[float, ...], UUID | None, float | None]:
            vector = engine.embed(image)
            raw = identify(vector, templates, candidates, MODEL_VERSION, Thresholds(-1, 1))
            return vector, raw.member_id, raw.score

        sample = capture(process, camera_index)
        vector, selected, score = sample.value
        # Impostor analysis is outside the latency measurement and never persisted per person.
        impostor = identify(
            vector, templates, candidates - {expected}, MODEL_VERSION, Thresholds(-1, 1)
        )
        # Ambiguous tied candidates cannot become a HIGH match during evaluation.
        return Trial(
            expected is not None,
            expected is not None and selected == expected,
            score if selected is not None else None,
            impostor.score,
            sample.seconds,
            sample.rejected,
        )

    for index, expected in enumerate(participants, 1):
        input(message("genuine_ready", number=index))
        for _ in range(repeats):
            trial = attempt(expected)
            trials.append(trial)
            print(message("attempt", seconds=f"{trial.processing_seconds:.3f}"))
    for index in range(1, unknown_people + 1):
        if not consent(message("unknown", number=index)):
            continue
        for _ in range(repeats):
            trial = attempt(None)
            trials.append(trial)
            print(message("attempt", seconds=f"{trial.processing_seconds:.3f}"))
    return trials


def model_provenance(directory: Path) -> dict[str, object]:
    manifest = json.loads((directory / "manifest.json").read_text())
    hashes = {}
    for name in ("sface.onnx", "yunet.onnx"):
        with (directory / name).open("rb") as model_file:
            digest = hashlib.file_digest(model_file, "sha256").hexdigest()
        if digest != manifest["files"][name]["sha256"]:
            raise ValueError("Model checksum differs from the approved local manifest")
        hashes[name] = digest
    return {"commit": manifest["commit"], "sha256": hashes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path("assets/models"))
    parser.add_argument(
        "--thresholds", type=Path, default=Path("assets/models/thresholds.example.json")
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--participants", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--unknown-people", type=int, default=3)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.participants < 2 or args.repeats < 1 or args.unknown_people < 1:
        parser.error("Require >=2 participants, >=1 repeats and >=1 unknown people")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = args.report or Path(f"data/evaluations/{stamp}.json")
    if report_path.exists():
        parser.error("Report exists; choose another path")
    settings = json.loads(args.thresholds.read_text())
    if settings.get("model_version") != MODEL_VERSION:
        parser.error("Threshold configuration must name sface_2021dec")
    starting = Thresholds(settings["medium"], settings["high"])
    provenance = model_provenance(args.models)
    engine = SFaceEngine(args.models / "yunet.onnx", args.models / "sface.onnx")
    templates: list[Template] = []
    participants: list[UUID] = []
    calibration: list[Trial] = []
    validation: list[Trial] = []
    print(message("intro"))
    if input(message("review_consent")).strip().lower() != "yes":
        print(message("not_started"))
        return
    try:
        for number in range(1, args.participants + 1):
            if not consent(message("participant", number=number)):
                continue
            member = uuid4()
            participants.append(member)
            for _ in range(3):
                sample = capture(engine.embed, args.camera)
                templates.append(Template(member, MODEL_VERSION, sample.value))
        if len(participants) < 2:
            print(message("too_few"))
            return
        print(message("calibration"))
        calibration = collect(
            engine, templates, participants, args.camera, args.repeats, args.unknown_people
        )
        candidate = recommend(calibration)
        if candidate is None:
            print(message("no_candidate"))
        else:
            print(message("candidate", medium=candidate.medium, high=candidate.high))
            input(message("validation"))
            validation = collect(
                engine, templates, participants, args.camera, args.repeats, args.unknown_people
            )
        report: dict[str, object] = {
            "schema_version": 1,
            "kind": "consented_webcam_evaluation",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "machine": machine_info(),
            "model_version": MODEL_VERSION,
            "models": provenance,
            "quality_settings": asdict(engine.quality),
            "enrolled_members": len(participants),
            "templates": len(templates),
            "starting_thresholds": asdict(starting),
            "calibration_at_starting_thresholds": asdict(summarize(calibration, starting)),
            "candidate_thresholds": asdict(candidate) if candidate else None,
            "calibration_at_candidate": asdict(summarize(calibration, candidate))
            if candidate
            else None,
            "validation_at_candidate": asdict(summarize(validation, candidate))
            if candidate
            else None,
            "timing_scope": (
                "JPEG encoding + detection/quality/alignment/embedding + full gallery matching; "
                "excludes human wait, camera acquisition and UI rendering"
            ),
            "consent_text_version": "m1-temporary-v0.2",
            "contains_biometrics": False,
            "m1_acceptance": "NOT VERIFIED",
            "limitations": [
                "Candidate thresholds require owner review and representative testing",
                (
                    "Known-participant capture rate excludes rejected frames; "
                    "rejections reported separately"
                ),
                "300-real-member timing and field validation still required",
            ],
        }
        write_report(report_path, report)
        print(message("report", path=report_path))
    except KeyboardInterrupt:
        print(message("cancelled"))
    finally:
        templates.clear()
        participants.clear()
        calibration.clear()
        validation.clear()


if __name__ == "__main__":
    main()
