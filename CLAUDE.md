# Event Auth — contributor instructions

## Read first
Before every task, read docs/design_dna.md, docs/General_Guidelines.md,
docs/Implementation_Plan.md, docs/Process_Flow.md and docs/Technical_Requirements.md
completely, plus docs/Demo_Scope.md, docs/Decisions_Log.md and docs/Current_Build.md.
Only explicit approved changes override older rules. Flag conflicts; never silently choose.
Use M1–M5, not the historical Flutter phases. Owner approved starting M2 while M1
volunteer validation is pending (2026-09-25); this does not waive face acceptance.
Owner confirmed M2 timing and authorized M3 with signed QR PDFs (2026-09-27),
deferring thermal integration. Owner continued to M4 development on 2026-09-28.
Owner authorized M5 preparation with camera testing deferred (2026-09-28).
Face recognition remains experimental; see M3_STATUS.md, M4_STATUS.md and M5_STATUS.md.

## Product
Offline community event registration, human-confirmed face identification, signed
printed entitlement coupons and one-time redemption. Current pilot: local laptop
server, browser clients, 300 members, one check-in desk, up to two counters.
Python/FastAPI + PostgreSQL + React/TypeScript; CPU ONNX models selected by owner.
English initially; no internet required at runtime. Local Wi-Fi required between devices.

## Six rules
1. Member ID is identity; face recognition finds it.
2. No internet required on event day.
3. A human confirms every match before printing.
4. One coupon per person per slot; redemption is atomic, never duplicated.
5. Face fallback is ID/name/mobile lookup; printer fallback is admin lookup redemption.
6. Food is one entitlement type; no food-specific rules in core.

## Protect the core
Configuration → reusable module → external customer add-on; never customer-specific core edits.
Core is generic plain Python: face interface, members, entitlements, roles and security.
Core must not import modules, config, framework, database driver or UI.
Runtime access is isolated in the injected face adapter; callers use the core interface.
Any shared core change needs a written PR reason and passing existing tests.
Inject persistence, face runtime, printing and crypto. Config cannot weaken security or redemption.

## Structure
backend/src/event_auth/
  core/                 # pure rules and ports
  adapters/             # database, face runtime, printer, crypto
  api/                  # HTTP transport and application wiring
  services/             # authorized application operations with injected adapters
  config/               # validated configuration
  modules/              # reusable food_coupon and data_import
backend/migrations/     # Alembic
backend/tests/          # core, HTTP, isolated PostgreSQL tests
frontend/src/           # React features, shared UI, l10n
assets/models/          # approved models/provenance, no real faces
assets/config/          # example customer configuration
docs/                   # source of truth

## Standards
Python 3.11+, FastAPI, SQLAlchemy/Alembic, PostgreSQL; React/TypeScript/Vite.
Ruff format/check, mypy, pytest; frontend formatter, ESLint, TypeScript, tests/build.
At least 80% core coverage. Explicit concurrency tests for redemption/reprint/closure.
Python snake_case; TypeScript camelCase; types/components PascalCase; tables plural snake_case.
UUID v4 internal IDs; short readable member/coupon codes. Versioned database migrations only.
No business logic in UI; all UI text in translation files; customer variation from config.
Flag new dependencies, verify commercial-friendly licences and offline behaviour.
Never download models at runtime. Owner chooses the face model before adoption.
Small purpose-specific PRs: what, why, tests and UI screenshots. Conventional commits.
No secrets, real personal data or face images in Git; only obviously fake test members.

## Privacy and security
Consent before capture, guardian consent for minors; ID-only path always available.
Store embeddings and one small reference photo, encrypted at rest. No raw photo galleries.
Delete all member personal data; retain anonymised coupon counts only.
No names, phone numbers, PINs or biometric data in logs; no telemetry.
Audit sensitive actions with actor ID, time and entity IDs, including issuance, redemption,
selection changes, imports and PIN resets. Enforce roles in services from the start.
Server only holds Ed25519 private key. Counter responses exclude photos/templates/mobile numbers.
Counters pause on connection loss. Lost-response retries recover the original outcome.
Reprint voids old and issues new atomically; print retry retains the same coupon.
Closing an event is final; outstanding coupons expire. Expired result: EXPIRED — DO NOT SERVE.
Pilot backup: passphrase-encrypted database plus recovery keys; successful restore test required.
Follow docs/SECURITY.md; draft consent requires owner review before pilot.

## Definition of done
Works without internet; follows Design DNA and all core boundaries.
Localized strings/configurable values; all relevant automated checks pass.
Sensitive actions audited; docs updated when behaviour changes.
Laptop validation during development; phone-browser and printer validation before pilot.
Zero HIGH false matches in consented test set; >=90% genuine HIGH/MEDIUM; <=1 second
identification at 300 members. Record 6,000-template scale benchmark without blocking pilot.
Before pilot: 20-person dry run, tested fresh-laptop setup and encrypted backup restore.
Never claim device/physical/accuracy checks passed without evidence.
