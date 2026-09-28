# M4 status — 2026-09-28

Implemented for local development following the owner's instruction to continue.
Signed PDF output remains the approved printer substitute. M1 accuracy validation,
M3 end-to-end timing and physical M4 acceptance are still pending; M5 has not started.

## Implemented
- Local QR decoding, browser camera and keyboard-input scanner path; server signature,
  event/slot, coupon status and counter-option checks. Atomic single redemption.
- Full-screen semantic results, configurable display timing and optional sound/vibration.
- Actor/action/request-scoped persistent receipts; changed-payload reuse rejected.
  An uncertain response pauses scans and preserves the request for retry. Recovered
  results are clearly separate from fresh SERVE instructions.
- Admin lookup redemption through the same validation, encrypted-reason void/replacement,
  final event closure and expiry. Replacement cancels the old QR in the same transaction;
  used entitlements cannot be reissued. PDF download retry retains the original coupon.
- Registered/checked-in/issued/served/fallback counts and per-option CSV. Replacement
  claims avoid double counting. Anonymous event-person IDs preserve distinct counts
  across multiple slots and member deletion. Personal snapshots/reasons are removed.
- Migration 0004 preserves existing signed coupons and backfills anonymous IDs.
  Existing signing/encryption keys are retained. No new M4 runtime dependencies.

## Automated evidence
- 128 backend tests passed against isolated PostgreSQL, none skipped; 100% core coverage
  (126 statements). Ruff formatting/lint and mypy pass.
- Six frontend tests pass; formatting, ESLint, TypeScript and production build pass.
- Tests cover two counters racing, same-key concurrency, duplicate scans, replay recovery,
  changed payload, rollback/retry, tampered QR, wrong slot/counter, replacement and closure
  races, permissions, counter-response privacy, encrypted reasons and full deletion.
- Migration downgrade/reapply tested with existing fake M3 coupons and multi-slot counts;
  no Alembic schema drift. Downgrade refuses to discard replacement history.
- PDF QR decoded locally and verified. Browser smoke uses fake members and extracted QR
  text, including SERVE, ALREADY USED, lost-response recovery, dashboard counts and narrow
  layout. It does not exercise physical cameras, scanners or real faces.
- Final real Chrome smoke passed for redemption, duplicate rejection, response-loss
  recovery, dashboard and existing role flows. Screenshot: screenshots/m4-serve.png.
- Existing local database upgraded from 0003 to 0004 with the original private keys.
  App restarted on 127.0.0.1:8000; UI/readiness returned 200 and unauthenticated counter
  access returned 401. No real coupons were redeemed or events closed by verification.
  The isolated test database was stopped after checks.
- Existing Starlette HTTPX and Alembic path_separator deprecation warnings remain.

## Shared core reason
The generic plain-Python redemption decision is centralized so QR and admin lookup
share the same event/status/scope/eligibility rules. Persistence, signing and UI stay
outside core. Existing tests and architecture boundaries continue to pass.

## Not yet verified
- Real QR camera/USB scanner reliability and scan-to-result <=1 second on intended devices.
- Physical two-counter operation over the event network; trusted phone HTTPS is M5 work.
- Formal consented face accuracy/calibration and 300-member full-pipeline timing. The
  owner's two-person success is functional feedback, not a measured acceptance dataset.
- M3 check-in <=15 seconds; deferred physical printer integration and printed-QR reliability.
- M5 encrypted backup restore, fresh-machine setup and 20-person end-to-end dry run.

Use M4_GUIDE.md for local testing. Do not close a real event just to test the UI.
