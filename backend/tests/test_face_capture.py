from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from event_auth.adapters.face.sface import CaptureRejected, Quality, SFaceEngine
from event_auth.services.enrollment import capture_error


@pytest.mark.parametrize(
    ("faces", "code"),
    [(None, "no_face"), (np.empty((0, 15)), "no_face"), (np.zeros((2, 15)), "one_person")],
)
def test_capture_distinguishes_missing_and_multiple_faces(faces, code):
    # Synthetic blank image only; no real biometric data in tests.
    ok, image = cv2.imencode(".jpg", np.zeros((480, 640, 3), dtype=np.uint8))
    assert ok
    engine = object.__new__(SFaceEngine)
    engine.quality = Quality()
    engine.detector = Mock()
    engine.detector.detect.return_value = (1, faces)
    engine.recognizer = Mock()

    with pytest.raises(CaptureRejected) as rejected:
        engine.embed(image.tobytes())

    assert capture_error(rejected.value) == code
    assert engine.detector.setInputSize.call_args_list[0].args == ((640, 480),)
    engine.recognizer.alignCrop.assert_not_called()
    engine.recognizer.feature.assert_not_called()


def test_scaled_retry_restores_box_and_all_landmarks():
    engine = object.__new__(SFaceEngine)
    engine.detector = Mock()
    face = np.array(
        [[10, 20, 100, 120, 30, 40, 70, 40, 50, 60, 35, 80, 65, 80, 0.95]], dtype=np.float32
    )
    engine.detector.detect.side_effect = [(1, None), (1, face)]
    result = engine._detect(np.zeros((480, 640, 3), dtype=np.uint8))
    np.testing.assert_allclose(result[:, :14], face[:, :14] * 2)
    np.testing.assert_allclose(result[:, 14], face[:, 14])
    assert engine.detector.detect.call_args_list[1].args[0].shape == (240, 320, 3)


def test_multiple_faces_do_not_trigger_smaller_retry():
    engine = object.__new__(SFaceEngine)
    engine.detector = Mock()
    faces = np.zeros((2, 15), dtype=np.float32)
    engine.detector.detect.return_value = (1, faces)
    assert engine._detect(np.zeros((480, 640, 3), dtype=np.uint8)) is faces
    engine.detector.detect.assert_called_once()


def test_second_scale_retry_restores_geometry_and_keeps_quality_gate():
    engine = object.__new__(SFaceEngine)
    engine.quality = Quality()
    engine.detector = Mock()
    engine.recognizer = Mock()
    face = np.array(
        [[80, 40, 60, 80, 95, 65, 125, 65, 110, 80, 98, 100, 122, 100, 0.903]], dtype=np.float32
    )
    engine.detector.detect.side_effect = [(1, None), (1, None), (1, face)]
    ok, encoded = cv2.imencode(".jpg", np.full((480, 640, 3), 100, dtype=np.uint8))
    assert ok
    with pytest.raises(CaptureRejected, match="Hold still"):
        engine.embed(encoded.tobytes())
    assert engine.detector.detect.call_args_list[-1].args[0].shape == (180, 240, 3)
    engine.recognizer.feature.assert_not_called()
