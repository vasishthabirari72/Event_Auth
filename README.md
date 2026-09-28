# Event Auth

Local laptop pilot: FastAPI, PostgreSQL and React, with SFace + YuNet CPU recognition.
M2 administration, M3 signed QR PDFs and M4 redemption/dashboard are implemented. M2 timing targets
were confirmed by the owner; face accuracy validation remains pending. Start with the
[M2 walkthrough](docs/M2_GUIDE.md), [M3 check-in](docs/M3_GUIDE.md), then
[M4 redemption](docs/M4_GUIDE.md) and [M5 preparation](docs/M5_GUIDE.md).
Read docs/Current_Build.md and docs/Decisions_Log.md before contributing.

## Installed in this workspace
Python 3.12 lives inside `.tools/python`; `.venv` contains backend dependencies.
Frontend dependencies are in `frontend/node_modules`. Model weights were provisioned
into `assets/models`; provenance and licence files are retained alongside them.
Docker Engine 29.8.1 and Compose v5.5.1 are installed. If an existing IDE terminal
reports Docker socket permission denied, reopen the IDE after logging out and back in
to refresh group membership. A new shell can also use `newgrp docker`.

## Fresh-machine setup
Install Python 3.12, uv, Node.js 22.12+ (or a compatible newer supported Node),
and Docker Engine with the Compose plugin. Downloads are setup-time only.

```sh
uv sync --locked
npm --prefix frontend ci
python scripts/download_models.py
cp -n .env.example .env
```

Choose a unique database password in `.env`, updating DATABASE_URL to match
(URL-encode special characters in its password). Never commit `.env`.

```sh
docker compose up -d --wait db
set -a
. ./.env
set +a
.venv/bin/alembic upgrade head
.venv/bin/event-auth-admin --username admin
.venv/bin/python -m event_auth.adapters.signing "$EVENT_AUTH_SIGNING_KEY_FILE"
npm --prefix frontend run build
.venv/bin/uvicorn event_auth.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open http://127.0.0.1:8000 and sign in with the username/PIN you just created.
The administrator command is run once; it creates a private encryption key outside
this project. Keep that key to recover encrypted records. No default production PIN. The signing command is also run once for a new installation;
never regenerate keys for existing coupons.
Experimental face enrollment is enabled in this workspace (owner approved 2026-09-27).
Save or select a member, then use Face registration → Add or replace face.
Accuracy validation is still pending; new configurations default to disabled.
`/api/health` is process liveness; `/api/ready` separately checks database connectivity.
For frontend development run `npm --prefix frontend run dev`; it proxies API requests.
Member, consent, import, staff and event endpoints require authenticated admin access.
Check-in is available to admin/check-in staff; redemption to admin/counter staff.
Provision the signing key using M3_GUIDE.md before issuance. Continue using localhost;
M5 must establish trusted HTTPS before phone/LAN deployment.

## Checks
```sh
.venv/bin/ruff format --check backend scripts
.venv/bin/ruff check backend scripts
.venv/bin/mypy
env -u PYTHONPATH .venv/bin/pytest
npm --prefix frontend run format:check
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
```

Unset PYTHONPATH to avoid unrelated ROS plugins installed on this development machine.
For PostgreSQL integration checks without creating a development `.env`:

```sh
POSTGRES_PASSWORD=unused_for_test_service docker compose --profile test up -d --wait test-db
export TEST_DATABASE_URL=postgresql+psycopg://event_auth_test:local_test_only@127.0.0.1:5433/event_auth_test
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/alembic upgrade head
env -u PYTHONPATH .venv/bin/pytest
```

The placeholder POSTGRES_PASSWORD only satisfies Compose parsing of the unstarted `db`
service; the isolated `test-db` uses its own test-only credentials. Only `test-db` starts.
Tests refuse a database not named `event_auth_test` and verify the migration revision.
No production/test data is shared. The test database is ephemeral (tmpfs).
Stop it after testing with
`POSTGRES_PASSWORD=unused_for_test_service docker compose --profile test stop test-db`.

## Consented face evaluation (local desktop)
Read docs/CONSENT_TEMPLATE.md and docs/MODEL_EVALUATION.md before using volunteers.
Run this yourself in a graphical desktop session; it opens the webcam only after consent.

```sh
.venv/bin/event-auth-face-test --thresholds assets/models/thresholds.example.json
```

The example thresholds are uncalibrated. The tool takes three enrollment frames per
consenting participant, calibration captures and separate validation captures, including
unenrolled people. Images/templates stay in memory; only aggregate reports are saved
under `data/evaluations/`. Stop with Escape/Ctrl-C. No volunteer capture has been performed
by the coding agent. Follow [the face test guide](docs/FACE_TEST_GUIDE.md).

For a camera-free synthetic matching benchmark:

```sh
.venv/bin/python -m event_auth.evaluation.benchmark --output data/evaluations/scale.json
```

Synthetic timing is not recognition accuracy or full-pipeline acceptance evidence.

## Still required
Consented face calibration and 300-member timing; M3 end-to-end timing; physical QR
scanning and M4 counter timing; M5 phone HTTPS/backup restore/dry run.
See docs/M2_STATUS.md for current evidence and docs/M2_GUIDE.md for fake demo data,
imports, optional experimental enrollment and the Chrome smoke test.
Thermal integration is deferred by the owner; current coupons are signed PDFs. mkcert
and phone trust setup are needed before M5, not for localhost development.

## M5 operator tools
Camera/phone testing is deferred; recovery and HTTPS tooling are available.
After loading `.env`, run `.venv/bin/python -m event_auth.operations.preflight`.
See [backup/restore and HTTPS setup](docs/M5_GUIDE.md), [staff guides](docs/STAFF_GUIDES.md)
and [pilot checklist](docs/PILOT_CHECKLIST.md). No new runtime package is required.
`mkcert` is needed when provisioning phone HTTPS, not for the current localhost app.
