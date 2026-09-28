import json
import math
from dataclasses import asdict
from uuid import uuid4

import pytest
from event_auth import face_lab
from event_auth.core.face.contracts import Template
from event_auth.core.face.matching import Thresholds
from event_auth.evaluation.benchmark import run_benchmark, synthetic_gallery, write_report
from event_auth.evaluation.metrics import Trial, recommend, summarize


def trial(score, correct=True, genuine=True, impostor=0.2):
    return Trial(genuine, correct, score, impostor, 0.25)


def test_calibration_and_held_out_failure_are_separate():
    calibration = [trial(0.8), trial(0.7), trial(0.3, False, False, 0.3)]
    candidate = recommend(calibration)
    assert candidate is not None
    assert candidate.medium == 0.7
    assert candidate.high > candidate.medium
    assert summarize(calibration, candidate).accuracy_targets_met_on_sample
    held_out = [trial(0.8), trial(0.5), trial(0.9, False, False, 0.9)]
    result = summarize(held_out, candidate)
    assert result.false_high == 1
    assert result.genuine_rate == 0.5
    assert not result.accuracy_targets_met_on_sample


def test_impostor_boundary_is_excluded_from_high():
    candidate = recommend([trial(0.8, impostor=0.85), trial(0.4, False, False, 0.4)])
    assert candidate is not None and candidate.high > 0.85
    result = summarize([trial(0.85, False, False, 0.85)], candidate)
    assert result.false_high == 0 and result.false_medium == 1


def test_thresholds_cannot_fix_wrong_identity():
    assert recommend([trial(0.9, False), trial(0.2, False, False)]) is None
    assert recommend([trial(0.8)]) is None
    assert recommend([trial(0.8), trial(1.0, False, False, 1.0)]) is None


def test_missing_trials_cannot_pass():
    thresholds = Thresholds(0.4, 0.8)
    assert not summarize([], thresholds).accuracy_targets_met_on_sample
    assert not summarize([trial(0.9)], thresholds).accuracy_targets_met_on_sample
    result = summarize([trial(None, False), trial(0.2, False, False)], thresholds)
    assert result.genuine_rate == 0
    assert result.max_seconds == 0.25


@pytest.mark.parametrize("score", [math.nan, math.inf, -1.1, 1.1])
def test_nonfinite_or_invalid_scores_rejected(score):
    with pytest.raises(ValueError):
        trial(score)


def test_synthetic_report_never_claims_accuracy():
    gallery, query = synthetic_gallery(2)
    assert len(gallery) == 6 and len(query) == 128
    assert len({t.member_id for t in gallery}) == 2
    report = run_benchmark((2,), repeats=2)
    assert not report["accuracy_evaluated"]
    assert not report["full_pipeline_evaluated"]
    assert report["m1_acceptance"] == "NOT VERIFIED"
    assert "vector" not in json.dumps(report)


def test_report_cannot_overwrite_existing_evidence(tmp_path):
    path = tmp_path / "report.json"
    write_report(path, {"aggregate": 1})
    with pytest.raises(FileExistsError):
        write_report(path, {"aggregate": 2})
    assert json.loads(path.read_text()) == {"aggregate": 1}


def test_consent_is_explicit(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert not face_lab.consent("Test")
    monkeypatch.setattr("builtins.input", lambda _: "guardian")
    assert face_lab.consent("Test")


def test_collect_unknowns_and_genuine_without_camera(monkeypatch):
    a, b = uuid4(), uuid4()
    templates = [Template(a, "sface_2021dec", (1.0, 0.0)), Template(b, "sface_2021dec", (0.0, 1.0))]
    vectors = iter([(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)])

    class Engine:
        def embed(self, _):
            return next(vectors)

    monkeypatch.setattr("builtins.input", lambda _: "adult")
    monkeypatch.setattr(
        face_lab, "capture", lambda process, _: face_lab.Captured(process(b"x"), 0.3, 2)
    )
    records = face_lab.collect(Engine(), templates, [a, b], 0, 1, 1)
    assert [t.correct_top for t in records] == [True, True, False]
    summary = summarize(records, Thresholds(0.4, 0.8))
    assert summary.genuine_attempts == 2 and summary.unknown_attempts == 1
    assert summary.rejected_captures == 6
    serialized = json.dumps(asdict(summary))
    assert str(a) not in serialized and str(b) not in serialized


def test_skip_unknown_never_opens_camera(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "skip")
    monkeypatch.setattr(face_lab, "capture", lambda *_: pytest.fail("Camera must stay closed"))
    assert face_lab.collect(None, [], [], 0, 1, 1) == []


def test_capture_includes_processing_and_releases_camera(monkeypatch):
    import numpy as np

    released = []

    class Camera:
        def isOpened(self):
            return True

        def read(self):
            return True, np.zeros((2, 2, 3), dtype=np.uint8)

        def release(self):
            released.append(True)

    monkeypatch.setattr(face_lab.cv2, "VideoCapture", lambda _: Camera())
    monkeypatch.setattr(face_lab.cv2, "imshow", lambda *_: None)
    monkeypatch.setattr(face_lab.cv2, "waitKey", lambda _: 32)
    monkeypatch.setattr(face_lab.cv2, "destroyAllWindows", lambda: None)
    clock = iter([10.0, 10.75])
    monkeypatch.setattr(face_lab.time, "perf_counter", lambda: next(clock))
    sample = face_lab.capture(lambda _: "processed", 0)
    assert sample.value == "processed" and sample.seconds == 0.75 and released == [True]


def test_aborted_capture_releases_camera(monkeypatch):
    released = []

    class Camera:
        def isOpened(self):
            return True

        def read(self):
            return True, object()

        def release(self):
            released.append(True)

    monkeypatch.setattr(face_lab.cv2, "VideoCapture", lambda _: Camera())
    monkeypatch.setattr(face_lab.cv2, "imshow", lambda *_: None)
    monkeypatch.setattr(face_lab.cv2, "waitKey", lambda _: 27)
    monkeypatch.setattr(face_lab.cv2, "destroyAllWindows", lambda: None)
    with pytest.raises(KeyboardInterrupt):
        face_lab.capture(lambda _: pytest.fail("Do not process cancelled capture"), 0)
    assert released == [True]


def test_lab_exports_aggregate_only_and_preserves_validation_failure(monkeypatch, tmp_path):
    from event_auth.adapters.face.sface import Quality

    settings = tmp_path / "thresholds.json"
    settings.write_text(json.dumps({"model_version": "sface_2021dec", "medium": 0.4, "high": 0.8}))
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "face-lab",
            "--participants",
            "2",
            "--thresholds",
            str(settings),
            "--report",
            str(report_path),
        ],
    )
    answers = iter(["yes", "adult", "guardian", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(face_lab, "model_provenance", lambda _: {"sha256": "test-only"})

    class Engine:
        quality = Quality()

        def embed(self, _):
            return (1.0, 0.0)

    monkeypatch.setattr(face_lab, "SFaceEngine", lambda *_: Engine())
    monkeypatch.setattr(
        face_lab, "capture", lambda process, _: face_lab.Captured(process(b"x"), 0.1, 0)
    )
    phases = iter(
        [
            [trial(0.8), trial(0.7), trial(0.3, False, False, 0.3)],
            [trial(0.8), trial(0.5), trial(0.9, False, False, 0.9)],
        ]
    )
    monkeypatch.setattr(face_lab, "collect", lambda *_: next(phases))
    face_lab.main()
    report = json.loads(report_path.read_text())
    assert report["calibration_at_candidate"]["accuracy_targets_met_on_sample"]
    assert not report["validation_at_candidate"]["accuracy_targets_met_on_sample"]
    assert report["m1_acceptance"] == "NOT VERIFIED"
    assert report["enrolled_members"] == 2 and report["templates"] == 6
    assert report["contains_biometrics"] is False
    assert "vector" not in report_path.read_text() and "member_id" not in report_path.read_text()


def test_model_integrity_rejects_changed_weights(tmp_path):
    import hashlib

    for name in ("sface.onnx", "yunet.onnx"):
        (tmp_path / name).write_bytes(b"synthetic-model-fixture")
    digest = hashlib.sha256(b"synthetic-model-fixture").hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "commit": "test",
                "files": {name: {"sha256": digest} for name in ("sface.onnx", "yunet.onnx")},
            }
        )
    )
    assert face_lab.model_provenance(tmp_path)["commit"] == "test"
    (tmp_path / "sface.onnx").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        face_lab.model_provenance(tmp_path)
