# M1 status — 2026-09-25

M1 volunteer validation is pending, not complete. The owner approved M2 development
without waiting for volunteers. See M2_STATUS.md for the current application.
The implementation/checks below record M1 history.

## Implemented and checked
- Lowercase docs directory; approved scope, nine decisions and model selection recorded.
- Python 3.12 project environment, dependency lock and pure core boundaries.
- FastAPI liveness/readiness, React setup UI with local-only camera preview.
- PostgreSQL Compose configuration and Alembic baseline (no member schema yet).
- Service-level role policy and version/event-scoped cosine matcher with configurable thresholds.
- Selected SFace/YuNet ONNX adapter, basic quality gates and consented in-memory webcam CLI.
- Model weights downloaded once, verified against publisher LFS hashes; licences and provenance retained.
- CI workflow added but not executed on a hosted runner.

Validation performed:
- Ruff formatting/lint and mypy passed.
- 45 backend tests passed, none skipped; 100% coverage of the currently implemented core (70 statements).
- Real PostgreSQL integration passed, including database isolation and migration-head verification.
- Docker Engine 29.8.1 and Compose v5.5.1 verified; this older IDE session used sg docker
  to apply the owner-configured Docker group membership.
- Two frontend tests passed; TypeScript, ESLint, formatting and production build passed.
- npm audit after dependency update: zero known vulnerabilities.
- Real ONNX files loaded and synthetic blank frame rejected; no real camera capture performed.
- Built frontend served by FastAPI; health 200 and unknown API 404.
- Database readiness returned 503 without a database and 200 ready with the PostgreSQL test service.
- Alembic baseline SQL generation and CLI help checked; baseline migration applied to
  the real isolated PostgreSQL test database. Only the baseline exists; no member schema yet.
- Tests pass with two deprecation warnings: Starlette HTTPX and Alembic path_separator.
- Temporary test container stopped after validation; restart and migrate it before the next run.

## Evaluation tooling added — 2026-09-25
- Webcam evaluation now separates calibration from fresh held-out validation, with
  explicit consent for enrolled volunteers and unknown-person attempts.
- Aggregate JSON reports contain counts, timing, candidate thresholds, hardware and
  verified model provenance; images, templates and participant identifiers are not saved.
- Processing timing includes JPEG encoding, detection, quality checks, alignment,
  embedding and gallery matching; camera acquisition and UI rendering remain unmeasured.
- Synthetic matcher benchmark on AMD Ryzen 7 7730U: approximately 24 ms p95 for
  300 members / 900 templates and 158 ms p95 for 2,000 members / 6,000 templates.
  This excludes model inference and does not establish recognition accuracy or M1 acceptance.
- Evidence: [synthetic benchmark](benchmarks/synthetic_matcher_2026-09-25.json).
- Operator instructions: [face test guide](FACE_TEST_GUIDE.md).
- Ruff and mypy passed; all 45 backend tests passed with real PostgreSQL integration.
  Frontend checks above are from the earlier validation; frontend code was unchanged.

## Outstanding acceptance work
- Review the temporary consent template with the organizer.
- Conduct webcam evaluation with at least ten consenting participants; collect independent
  genuine and unknown-person attempts; calibrate HIGH/MEDIUM thresholds and quality settings.
- Measure full good-frame-to-result time at 300 members; benchmark 6,000 templates separately.
- Record real test results, laptop specifications and calibrated model configuration.
- Camera permissions, physical UI appearance and recognition quality have not been validated
  in a real graphical browser/volunteer session by the coding agent.

At the M1 checkpoint the UI was setup-only. M2 now adds login, encrypted member storage,
imports and events; coupons, redemption and backup remain later milestones.
The face CLI does not save images/templates and is not a substitute for permanent consent records.
