# AI Agent Prompts — approved laptop pilot

These prompts follow M1–M5 in `Demo_Scope.md`, the confirmed decisions in
`Decisions_Log.md`, and the architecture/standards in `Current_Build.md`.
They replace the original phone-app phase prompts. Prompt text is a template;
reading this file does not execute every prompt or authorize later milestones.

Owner-approved exception (2026-09-25): proceed with M2 while M1 volunteer validation
is pending. This overrides the M1-before-M2 gates below only. Face acceptance remains
required and recognition stays experimental. Current evidence is in M2_STATUS.md.

Owner update (2026-09-27): M2 timing targets confirmed; M3 development authorized
with signed QR PDFs and a future printer adapter boundary. Thermal hardware acceptance
is deferred. M1 accuracy and calibrated recognition thresholds are still pending.

Owner update (2026-09-28): continue M4 development after a successful owner-reported
two-person recognition trial. This permits development while physical/timing acceptance
is pending; it does not waive those checks. See M4_STATUS.md. Owner subsequently authorized M5 preparation while deferring camera testing;
see M5_STATUS.md. Physical acceptance remains pending.

## How to use

- Kickoff is already complete. Use Resume or the current milestone prompt.
- Copy the shared preamble together with the chosen prompt into a new session.
- Inspect existing work first; extend it instead of restarting or overwriting it.
- Give a short implementation plan, then proceed within already-authorized scope.
  Ask only for unresolved product choices, necessary missing input or actual permissions.
- Work milestone by milestone. Verify the preceding acceptance gate before advancing.
- Report criteria as PASS, FAIL or NOT VERIFIED with evidence. Missing hardware,
  volunteers or services means NOT VERIFIED, never an invented success.
- Run the milestone review before moving on. Current progress is in `M1_STATUS.md`;
  inspect the repository to confirm whether that status has since changed.

## Shared preamble — include with every prompt

```text
Read CLAUDE.md and these source documents completely before working:
- docs/design_dna.md
- docs/General_Guidelines.md
- docs/Implementation_Plan.md
- docs/Process_Flow.md
- docs/Technical_Requirements.md
- docs/Demo_Scope.md
- docs/Decisions_Log.md
- docs/Current_Build.md

Explicit owner-approved changes override only the affected older requirements.
All other core-protection, accessibility, testing and privacy rules remain binding.
Flag unresolved conflicts instead of silently choosing. Use milestones M1–M5.

Current stack: Python 3.12, FastAPI, PostgreSQL via SQLAlchemy/Alembic,
React/TypeScript/Vite, and local CPU ONNX inference. SFace + YuNet are already
selected by the owner. Do not restart model selection without a concrete reason.
Consult docs/DEPENDENCIES.md and docs/MODEL_EVALUATION.md before dependency/model changes.
Flag new dependencies and check their licences and offline behaviour.

Core is plain Python at backend/src/event_auth/core. It cannot import framework,
database driver, config loader, modules or UI. Inject platform services through
interfaces; only the face adapter calls the model runtime. Never hardcode food,
a customer or an event type in core. Customer requests follow configuration,
then reusable module, then external add-on; never customer-specific core edits.
Document the reason for shared core changes and preserve existing tests.

Member ID is identity; a human confirms every face match. One coupon per person
per entitlement slot, one redemption. Face failure has ID/name/mobile fallback;
printer failure has admin lookup redemption. The laptop server makes every
redemption decision. Local Wi-Fi is required; internet is not required at runtime.
Provision dependencies, models and assets beforehand. No runtime downloads or telemetry.

Consent precedes capture; under-18s need recorded guardian consent. Keep an ID-only
path. Encrypt embeddings and the one reference thumbnail at rest. Delete all member
personal data, retaining anonymised coupon counts only. Never log names, phone numbers,
PINs or face data. Audit sensitive actions using actor/time/entity IDs.

Keep English strings in translation files and customer-variable values in config.
Follow Design DNA for accessible touch targets, contrast, result words/icons and
at most two event-day actions. No business logic in React components.

Validate relevant changes with Ruff formatting/lint, mypy, pytest (at least 80%
core coverage), frontend formatting, ESLint, TypeScript, tests and production build.
Use a separate PostgreSQL test database; never substitute SQLite or test on live data.
Use obviously fake fixtures. Never commit real member/face data or secrets.
Report physical tests separately from automated checks. Update docs when behaviour changes.
```

## M1 — finish the skeleton and face evaluation

```text
Continue M1 from the existing implementation. Read docs/M1_STATUS.md, README.md,
docs/MODEL_EVALUATION.md and docs/CONSENT_TEMPLATE.md in addition to the preamble.
Inspect what exists and report remaining work before changing it.

Tasks:
1. Finish and verify the Python/React skeleton, dependency locks, local PostgreSQL
   setup, migrations, CI and architecture boundaries. Keep role policies in core
   from the start; do not expose member workflows before M2 authentication.
2. Use the approved SFace + YuNet models locally. Preserve model licences,
   exact source revision and hashes. No automatic model downloads during use.
3. Complete a consented evaluation tool: three good enrollment frames, face size,
   blur, brightness and frontal quality gates, alignment, normalized embeddings,
   event-candidate/model-version filtering, and configurable HIGH/MEDIUM thresholds.
   Keep computation responsive. Liveness is deferred for this pilot.
4. Keep temporary evaluation data in memory; do not silently turn the POC into a
   persistent registry. Consent and guardian-consent rules still apply.
5. Provide reproducible calibration/benchmark tooling and operator instructions.
   Use separate enrollment/evaluation captures and genuine/unknown-person attempts.
   Synthetic templates may establish scale timings, not recognition accuracy.

Acceptance:
- Enroll ten consenting participants and identify each within one second on the laptop.
- Zero HIGH false matches in the consented test set; at least 90% of genuine attempts
  reach HIGH or MEDIUM in normal indoor lighting.
- Good-frame-to-result identification within one second at 300 members on the pilot
  laptop, including detection, embedding and matching; do not report matcher-only
  timing as end-to-end timing.
- Record an informational 2,000-member / 6,000-template benchmark, not a pilot blocker.
- Record tested hardware, trial counts, model/config versions, measured results and
  calibrated thresholds. Uncalibrated example values do not satisfy this criterion.

Complete independent tooling work while hardware/volunteer checks are pending.
Tell the owner exactly what they need to install or run. Do not mark M1 complete
or move to M2 while required acceptance checks remain unverified.
```

## M2 — members, consent, login and events

```text
Implement M2 after checking M1 acceptance evidence. Preserve and extend the existing
core, face adapter, database setup and frontend. Read docs/SECURITY.md as well.

Build:
- Staff PIN login with admin/checkin/counter roles enforced in services, protected
  sessions and PIN handling. Admin staff-PIN resets are audited.
- PostgreSQL schema and Alembic migrations for staff, members, consents, encrypted
  face templates/reference thumbnails, events, generic entitlement slots/options,
  counters, event registrations, selections and audit records needed by this milestone.
- Config-driven member forms, search, edit and full deletion. Persistent members
  are reused across events; collect choices per event. ID-only registration is available.
- Consent purpose, text version, date, consenting person and capturing staff;
  guardian consent for minors before capture. Draft text is a template for owner review.
- Three-frame capture with live quality hints, retake and duplicate-face admin review;
  retain model version and keep template matching version-compatible.
- Excel/CSV import of details and event choices; validate rows and report errors.
  Imported details do not imply biometric consent. Audit imports and selection changes.
- Event setup: name/date/venue, generic slots/options, counters and served options,
  registrations and choices. Only admins may change choices at any event status.
- Safe obviously fake demo data without real faces; counts-only CSV export where needed.

Keep food wording in config/module/UI. Households, attendance-only events, product
licensing, local-language translations and multi-customer tooling remain deferred.
Deleting a member removes all personal data and face data; any retained counts are
anonymised. No photos/templates/mobile numbers in counter responses.

Acceptance: registration with face <=90 seconds; event setup with choices <=5 minutes;
no capture without consent; guardian and ID-only paths work; duplicate review and
complete deletion work; roles cannot be bypassed through APIs; imports and counts
are correct. Include encryption, migration and audit tests, not only UI tests.
```

## M3 — check-in, fallback and printing

```text
Implement M3 after verifying M2 acceptance. Inspect the selected printer information;
if the model/interface is still unknown, ask for it while continuing independent work.
The owner supplies a thermal printer before physical M3 acceptance testing.

Build:
- Face check-in against this event's registered members, using calibrated thresholds.
- HIGH: show identity/reference photo and Confirm & Print. MEDIUM: Yes/No only;
  No leads to search. NO MATCH: Retry/Search. Human confirmation is always required.
- Fallback ID/name/mobile search and human identity verification, including the
  documented member-card/committee route for ID-only members. Tag method=fallback.
- Block a second coupon for the same person/slot. Preserve eligibility after redemption;
  never issue another entitlement merely because the original was redeemed.
- Save ISSUED before printing. Ed25519 signing is server-side; private keys never reach
  browsers. Follow the signed QR format and the Design DNA slip layout.
- ESC/POS printing from the laptop over USB or network for the chosen 58/80mm printer.
  Printer tests and errors have clear next steps. No Bluetooth printing requirement.
- Failed-print retry uses the same coupon code; record print_count and last_printed_at
  with clearly documented semantics. Handle uncertain printer acknowledgements safely.
- Prepare the admin lookup path for the M4 redemption service when printing fails;
  never create an independent redemption shortcut to bypass shared checks.

No mobile number, address or face image appears on a slip. Audit issuance and sensitive
changes. Test concurrent issuance, failed-print retries, tampered signatures, crash/restart
and role boundaries. No automatic printing from face recognition alone.

Acceptance: complete face check-in including print <=15 seconds; second issuance is
blocked; actual printed QR scans reliably; saved coupons survive restart. Report real
printer measurements separately from mocked printer tests.
```

## M4 — redemption, exceptions, dashboard and closure

```text
Implement M4 after verifying M3 acceptance. The laptop server is the sole authority;
there is no standalone counter or phone-to-phone sync mode.

Build:
- Browser QR scanning and optional keyboard-input USB scanner support.
- Server checks signature, event/slot, current status and counter-option eligibility;
  atomically change ISSUED to REDEEMED only once.
- Full-screen SERVE, ALREADY USED, INVALID, CANCELLED, WRONG COUNTER and red
  EXPIRED — DO NOT SERVE results, with text/icons and configured return timing.
- On connection loss pause and show: Reconnecting - send to admin desk.
  Do not serve locally or reconcile independent redemptions later.
- Lost-response retries recover the original result without another redemption.
  Distinguish recovery from a new serving instruction so retries do not cause two servings.
- Admin reprint atomically voids the old coupon and creates its replacement; void
  with reason; lookup/history; admin redemption by lookup when printing fails.
  Lookup uses the same eligibility, slot, status and one-time redemption rules.
- Admin dashboard: registered, checked in, served, option counts and fallback count;
  counts-only CSV. Reprints must not inflate unique check-in counts.
- Closing an event atomically expires all remaining ISSUED coupons. Closure is final
  for the pilot; no reopening and no redemption/issuance after closure.
- Audit issuance, redemption, reprint, void, selection changes, imports, PIN resets,
  event closure and existing sensitive actions with actor/time/entity IDs only.

Tests: two counters scanning together produce exactly one successful redemption;
replayed requests do not mutate again; changed-payload request-key reuse is rejected;
redemption racing with reprint or closure cannot produce incompatible outcomes.
Test rollback, wrong counter, expired/voided/tampered slips, lookup permissions and
counter-response privacy. A redeemed entitlement cannot be reissued through reprint.

Acceptance: exactly one SERVE for duplicate/concurrent scans, counts correct against
fixtures, exceptions and audit correct, and disconnection never permits serving.
Measure counter scan-to-result time against the retained <=1-second target.
```

## M5 — pilot readiness

```text
Implement M5 after verifying M4 acceptance. Pilot target: about 300 members,
one check-in desk and up to two food counters.

Tasks:
- Configure and document trusted LAN HTTPS, stable local address and phone-browser
  camera permissions. No internet is needed at the event. Test supported phones.
- Verify server role checks, session/PIN protection, encrypted biometric storage,
  server-only signing keys, minimal counter responses and logs without personal data.
- Create a passphrase-encrypted backup archive containing the PostgreSQL dump and
  recovery keys, plus other configuration needed to restore operation. No backup UI
  is required. Never leave an unencrypted database/key bundle on the USB drive.
- Restore into a separate fresh environment and verify data, key recovery, encrypted
  face-data readability and coupon state. Do not overwrite the running event database.
- Validate restart/crash recovery, lost-response retries and concurrent operations.
- Run a 20-person end-to-end dry run with actual devices, printer and local network;
  confirm no duplicate servings or data loss and correct dashboard counts.
- Test setup instructions on a fresh laptop and run the entire demo in under ten minutes.
- Write a short guide for each role and a pilot checklist covering power, router,
  printer/paper, staff access, test scans and backup/restore readiness.
- Ensure the owner has reviewed consent wording before the pilot. Identify remaining
  policy work, such as retention/restored-backup deletion, without inventing approval.

Report each criterion with evidence, remaining failures and missing physical tests.
Acceptance requires the 20-person dry run without errors, tested fresh-laptop setup,
phone/printer validation and a successful encrypted backup restore.
Do not add cloud deployment, licensing, liveness, households, PDF reporting or local
translations under the heading of hardening; those remain deferred.
```

## Milestone review — read-only

```text
Review the current milestone against Demo_Scope.md, Decisions_Log.md and Current_Build.md.
Inspect implementation and evidence; do not assume a milestone is complete from its label.

Check core import boundaries and injected adapters; generic entitlement rules; role
checks; consent/guardian/ID-only paths; full deletion/anonymisation; encryption and
server-only keys; complete audit coverage; privacy of logs and counter responses;
localised strings and accessible UI; no runtime internet dependency.
For coupon milestones, inspect atomic issuance/redemption/reprint/closure, retry
recovery, admin lookup fallback and disconnected counter behaviour.

Run applicable checks from README.md, including isolated PostgreSQL tests when available.
Report skipped/unavailable checks explicitly. Review coverage quality as well as percentage.
Physical face/printer/phone/restore acceptance requires its own recorded evidence.

List findings by severity with file references and suggested corrections. This prompt
is a review only: do not apply code fixes unless separately authorized. Report whether
required milestone acceptance gates are met and update the status report if requested.
```

## Resume approved work

```text
Read the shared preamble, README.md and the latest milestone status. Inspect repository
state and git history if available. Summarise the current milestone, completed work,
remaining criteria and blockers. Continue already-authorized work within that milestone;
do not restart kickoff, reselect SFace/YuNet or skip an unmet acceptance gate.
Ask for missing hardware/access/product input only where needed, while progressing
independent work. Never turn a missing physical test into a claimed pass.
```

## Fix a bug

```text
Bug: [symptom, steps, expected behaviour, device/browser]
Read the shared preamble. Find the root cause, explain the intended correction, then
implement and verify the fix within this request's scope. Add a meaningful regression
test where warranted. A shared core fix needs a written reason and passing existing tests;
a customer-specific request must use config/module/add-on instead. Flag requirement
conflicts and unresolved product choices before making dependent changes.
```

## Evaluate a customer request

```text
Request: [description]
Read the shared preamble. Evaluate configuration first, then a reusable module, then
an external add-on. Never propose customer-specific core changes. State whether the
request is inside the current pilot scope, estimate effort and show the proposed change.
This is an evaluation request, not permission to implement deferred features.
```

## Prepare a pilot configuration

```text
Pilot details: [organisation, branding, registration fields, slots/options, counters]
Read the shared preamble. Use the existing supported configuration schema and setup
scripts; first check that the needed milestone features are implemented. Validate the
configuration and provide laptop/server, browser, LAN HTTPS and USB/network-printer
setup steps. Keep English and per-person entitlements. Explain any unsupported request.
Do not generate product licence files or create multi-customer tooling. Keep operational
keys out of source control and do not modify core for this pilot.
```

## Explain the code

```text
Explain [feature or file] in plain language: what it does, where it connects to the
system, what is implemented and what remains incomplete. Use a small diagram only
if useful. Do not change code for this explanation request.
```
