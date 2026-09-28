# M1 model evaluation

Owner selected the free SFace + YuNet combination on 2026-09-24.

| Candidate | Published licence | Decision |
|---|---|---|
| OpenCV Zoo SFace (MobileFaceNet, ONNX) | Apache-2.0 for all files in the model directory | Selected for CPU evaluation |
| fal AuraFace v1 (ResNet100, ONNX) | Apache-2.0, publisher states commercial-use intent | Alternative; CPU timing not evaluated |
| InsightFace distributed pretrained models | Non-commercial research unless separately licensed | Excluded from this free commercial pilot |

Sources checked 2026-09-24:
- https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE (MIT detector)
- https://huggingface.co/fal/AuraFace-v1
- https://github.com/deepinsight/insightface/tree/master/python-package

Published model licences are recorded here; this is not an independent audit of training-data rights.
Provisioning saves the repository revision, model SHA-256s, sizes and licence texts.
The runtime uses OpenCV's CPU ONNX execution, not a cloud API. It cannot download models.
Only the face adapter imports the recognition runtime. Camera acquisition remains outside it.

## Evaluation protocol
The CLI is a development-only, in-memory tool, not registration. It asks for adult or
guardian consent before opening the camera for each enrollment. It uses anonymous
participant numbers, persists only aggregate evaluation reports, and does not retain
images or templates. The operator confirms consent-template review before enrollment.
No real face capture is automated by the coding agent.

Start with 10 consenting volunteers, three independent good enrollment frames each,
then separate genuine captures. Add independent unknown-person/impostor attempts and
varied normal indoor lighting before final calibration. Record exact model/config
versions, laptop CPU and memory, trial counts, HIGH false matches, genuine HIGH/MEDIUM
rate and good-frame-to-result latency. Do not reuse enrollment frames as evaluation.
The example thresholds are exploratory, explicitly uncalibrated and not pilot defaults.
The CLI now measures encoding, detection, quality, alignment, embedding and matching.
Human waiting, frame acquisition and UI rendering are excluded. It separately collects
calibration and fresh validation captures, including unknown people. Reports retain
NOT VERIFIED for M1; candidate thresholds are not automatically approved.
See FACE_TEST_GUIDE.md for commands and interpretation.
The separate synthetic benchmark measures matching only, without model inference.

## Acceptance (pending real evaluation)
- Zero HIGH false matches on the consented evaluation set.
- >=90% genuine attempts in HIGH/MEDIUM in normal indoor lighting.
- <=1 second good frame to result with 300 members on the pilot laptop.
- Informational benchmark at 2,000 members / 6,000 templates.
- Written calibrated thresholds and report; owner review before progressing beyond M1.
