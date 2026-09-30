# Current build — laptop pilot

## Authority
Read all five original documents plus Demo_Scope.md, Decisions_Log.md and this file
before any task. Explicit owner decisions take precedence; unchanged original rules
remain binding. Never silently resolve conflicts. The older phase plan and Flutter
stack are historical; use milestones M1–M5 from Demo_Scope.md.

## Stack and boundaries
Python 3.11+ / FastAPI; PostgreSQL via SQLAlchemy and Alembic; React/TypeScript/Vite.
Plain Python core owns rules and interfaces. It imports no framework, persistence,
configuration or UI code. Infrastructure implements injected ports. Only the face
subsystem's adapter may call a model runtime, through the public core face interface.
This explicitly relocates the original core/face runtime implementation to an adapter
so the no-platform-dependency rule is maintained. No customer-specific core edits.
Configuration → reusable module → external add-on remains the customization order.

## Folders
- backend/src/event_auth/core/: face, members, entitlements and security rules/ports.
- backend/src/event_auth/adapters/: database, face runtime, printer and crypto implementations.
- backend/src/event_auth/api/: HTTP transport and dependency wiring.
- backend/src/event_auth/config/: validated configuration loading.
- backend/src/event_auth/modules/: reusable food coupon and import modules.
- backend/migrations/: versioned schema changes.
- backend/tests/: core unit tests, HTTP and PostgreSQL integration tests.
- frontend/src/: feature UI, shared components and local translation files.
- assets/models/: approved local models and provenance; no automatic runtime downloads.
- docs/: requirements, decisions, security, setup and validation records.

## Standards and done
Python snake_case; TypeScript camelCase and PascalCase components. Generic entitlement
slots/options in core; strings in translations and customer variation in config.
Run Ruff format/check, mypy, pytest with >=80% core coverage, frontend formatting,
ESLint, TypeScript checking, tests and production build. Test PostgreSQL operations
against an isolated test database, never the live database. No SQLite substitution.
No network resources in the running UI or face pipeline. Installation may download
dependencies/models before the event; fully provision and test disconnected operation.
Sensitive actions are audited with IDs only. Require consent before face capture,
guardian consent for minors, ID-only registration and full personal-data deletion.
Face data is encrypted at rest. Server alone holds signing keys. Local Wi-Fi is
required, internet is not. Disconnected counters stop; no independent redemption.
Single-use rules cover retry, reprint and closure races; repeated requests must not
cause volunteers to serve twice. Admin lookup redemption shares normal validation.
Laptop checks during development; real phone, printer, 20-person dry run and encrypted
backup restore before pilot. Never claim unperformed physical tests passed.

## Milestone status
M1 validation pending. Owner selected SFace + YuNet; tooling is implemented.
M1 acceptance is not met by synthetic unit tests or a camera preview alone.
M2 implementation and automated checks are available; see M2_STATUS.md and M2_GUIDE.md.
The owner's 2026-09-25 decision overrides the M1-before-M2 gate in agent prompts.
Owner enabled experimental face enrollment in the workspace configuration on 2026-09-27.
New configs still default to disabled. Owner confirmed M2 timing targets on 2026-09-27.
M3 development is now authorized with signed QR PDF output instead of a thermal printer.
M1 accuracy remains pending; M3 identification is experimental. Owner reported successful
recognition with two people after cleaning the camera; this is not formal accuracy evidence.
Following the owner’s instruction to continue, M4 development is implemented. Owner authorized M5 preparation while camera testing
is deferred. Recovery/HTTPS tooling and staff guides are in M5_GUIDE.md; see M5_STATUS.md
for evidence. Physical acceptance and pilot readiness remain pending.
See M4_GUIDE.md and M4_STATUS.md for redemption, administration and pending physical checks.
See M3_GUIDE.md for setup and M3_STATUS.md for evidence and remaining acceptance.

## Member food defaults — approved 2026-09-30
The owner approved including every saved member automatically in each new event.
This supersedes earlier instructions to enter food choices separately for every event.
Admins set Default food option in Members; it is stored in the encrypted personal record.
New events copy that preference into each slot when its label uniquely matches an
option (ignoring case and surrounding spaces). Missing or unavailable defaults are
marked Needs choice; resolve these before marking ready or starting check-in.

Admins can override one event's choices in Events or use the Check-in shortcut before
scanning. This does not change the member default or other events. Changing a member
default affects future events only. For older events or members added later, use
Add missing members and fill missing defaults; existing selections are preserved.
Closed events cannot change. Changes do not rewrite issued coupons; use the existing
admin replacement process when necessary.

CSV/XLSX member imports accept optional default_option; old templates still work.
No migration or new dependency is needed. The reusable preferences module and
application services implement this; core rules remain unchanged. Review event
slots/options/counters before saving: automatic registrations activate the existing
structure lock immediately when members exist.

Validation for member defaults: 140/141 backend tests passed on the full run,
including all five new preference regressions; core coverage 100%. The existing
random-key PDF QR round-trip test failed decoding once, then both PDF/signing tests
passed on an isolated rerun. This intermittent QR decode issue remains to monitor.
Frontend: six tests, lint, type-check/build and Chrome smoke passed; browser smoke
checks automatic inclusion, prefilled Veg default and event-only Jain override.
Ruff, mypy and diff whitespace checks passed. No live member choices were migrated.
