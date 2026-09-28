# M1 volunteer face test

This tests recognition tooling on the laptop. It is not member registration and does
not print or redeem coupons. No new installation is required if README setup is complete.
Docker is not needed for this temporary, memory-only face test.

## Before starting

1. Review `CONSENT_TEMPLATE.md` with the organizer and explain it to each volunteer.
2. Arrange ten enrolled volunteers plus three people who will remain unenrolled.
   Prefer additional different unenrolled people for validation if available.
3. Use normal indoor lighting and a working laptop webcam. Include varied ages and
   glasses where practical; under-18s require a parent/guardian's permission.
4. Close other applications using the camera. Run from a graphical desktop terminal
   in the project root. Do not run the command through a headless SSH session.
5. Decide an order for participants; remember their numbers without saving names or
   a personal-data roster in the repository. Anyone may decline or stop.

## Run

```sh
.venv/bin/event-auth-face-test --participants 10 --unknown-people 3 --repeats 2
```

The tool checks the local model hashes, asks you to confirm you reviewed the consent
text, and then asks for `adult`, `guardian`, or `skip` for each enrollment.
The camera opens only after a valid consent answer. Each participant provides three
separate frames: press Space to capture. Adjust lighting/position if a quality hint
appears. Escape or Ctrl-C cancels and releases the camera; no report is written.

Keep the same enrollment order throughout. Reposition between captures; do not reuse
saved enrollment pictures. No images or templates are written to disk.

## Calibration and validation

- Calibration: each enrolled person returns for two fresh captures. Then the three
  unenrolled people each consent and provide two captures, without being enrolled.
- The tool recommends MEDIUM/HIGH thresholds from calibration observations. If correct
  top-ranked identities cannot reach 90%, or a safe HIGH threshold is unavailable,
  it records that no usable recommendation could be made.
- Validation: if a recommendation exists, collect another round of fresh captures
  from enrolled and unenrolled people. Thresholds remain fixed. Calibration captures
  are never counted as validation captures. The current gallery stays in memory.
- Use different unenrolled people in validation when possible and repeat under varied
  realistic lighting later. A small same-session sample is not representative field proof.

The automatic report is written under `data/evaluations/` (ignored by Git). You may
choose a path with `--report data/evaluations/my-session.json`; existing files are never
overwritten. It contains aggregate counts/rates, timing, model hashes, quality settings,
laptop hardware metadata and candidate thresholds, but no individual identities,
images, templates or per-person similarity scores.

A report includes both calibration and separate validation results. Failed validation
must not be fixed by tuning on those same validation samples; collect new holdout captures.
Candidate thresholds are not automatically installed into the application or approved.
All reports keep M1 acceptance as NOT VERIFIED pending review and remaining physical checks.

## What timing means

Per-capture timing starts at JPEG encoding and includes face detection, quality checks,
alignment, embedding and full-gallery matching. It excludes human waiting, camera frame
acquisition, UI rendering, and extra calibration-only impostor analysis.
Quality-rejected frames are counted separately; the genuine recognition rate is computed
on accepted captures, so inspect rejection counts as well as the recognition percentage.
This CLI host-processing measure does not establish the browser's good-frame-to-card time.
A ten-person result does not establish performance with 300 real event members.

The synthetic scale test requires no camera or volunteers:

```sh
.venv/bin/python -m event_auth.evaluation.benchmark --output data/evaluations/scale.json
```

It exercises 300 members / 900 templates and 2,000 members / 6,000 templates. These are
random synthetic vectors, not real faces. It measures matching only, not recognition
accuracy or full-pipeline latency. One warmup plus ten measured repetitions per size;
percentiles use the nearest-rank method. The seed and hardware are included for comparison.

## Next review

Share the aggregate report contents, not face images or templates. We will review:
- independent validation HIGH false matches (target zero on the tested sample);
- genuine HIGH/MEDIUM rate (target >=90%) and quality-rejection counts;
- full processing timings and remaining 300-member good-frame-to-result validation;
- exact model/config versions, representative trial coverage and calibrated configuration.

M1 remains incomplete until its real-world acceptance evidence is available.
