# M3 status — 2026-09-27

Implemented for local development with signed QR PDF output, explicitly requested by
owner. Physical thermal integration is deferred. M1 recognition calibration/volunteer
acceptance is pending; M3 is not a claim of event or pilot readiness. M4 development subsequently proceeded; see M4_STATUS.md.

## Implemented
- Admin starts READY events; check-in staff select a LIVE event and slot.
- Event-scoped and model-version-compatible recognition using current consented templates.
  HIGH and MEDIUM require human confirmation; NO MATCH offers retry/search.
- Optional face scan with participant agreement, reference photo alongside the camera,
  and ID/name/mobile fallback restricted to event members. Counter role denied access.
- Short-lived actor-bound confirmation tickets; confirmation rechecks eligibility,
  event state, selected option and face consent. Concurrent issuance has one winner.
- One coupon per member/slot, including after redemption. Repeating an already-completed
  confirmation recovers the original coupon, rather than issuing another one.
- Server-only Ed25519 signing with a separately provisioned 0600 private file. No runtime
  key generation, key replacement, remote service or device-side private keys.
- Coupon snapshots encrypted with the existing Vault. PDF generated in memory after issue
  commits; retries use the same signed QR and coupon code. Member deletion removes the
  encrypted snapshot and member link, retaining only anonymous entitlement counts.
- Generic document/output port for future printer adapters. Current render counters are
  successful server PDF renders, not physical print or browser-delivery acknowledgements.

## Evidence
- 106 backend tests passed on the isolated PostgreSQL database; none skipped.
  100% core coverage (112 statements); architecture boundary, lint/format and mypy pass.
- Six frontend tests; formatting, ESLint, TypeScript and production build pass.
- Tests cover event/role scope, explicit confirmation, HIGH/MEDIUM/NO MATCH, withdrawn
  consent, changed selections, expiry, concurrency, PDF render failure/retry, encrypted
  snapshots, full deletion, already-redeemed blocking and a fresh application instance.
- PDF rasterized with pdftoppm and its QR decoded by OpenCV; original Ed25519 signature
  verified. Tampering rejected. Private key reload/permissions/symlink rejection tested.
- Real headless Chrome with obviously fake members: admin login, event setup, LIVE,
  fallback search, confirmation, actual PDF download, repeat check-in blocked, responsive
  layout and volunteer boundary. Screenshot: screenshots/m3-pdf.png.
  Browser tests do not use real faces or assert camera recognition accuracy.
- Migration 0003 downgraded/reapplied on the empty test database; no schema drift.
- Local existing database upgraded additively from 0002 to 0003. Private signing key
  provisioned outside the source tree; local .env points to it. App ready on localhost,
  new routes reject unauthenticated requests. Real members/events were not modified by tests.
- Two pre-existing deprecation warnings: Starlette HTTPX and Alembic path_separator.

## Shared core reason
Added only a plain-Python CouponDocument and DocumentOutput protocol so all output
adapters consume the same coupon data without coupling issuance to a printer or PDF
library. No customer-specific behavior or platform import was added to core.

## Still pending
- M1 real calibrated thresholds, genuine/unknown-person accuracy and laptop speed testing.
- Owner trial of fresh-camera identification, confirmation and PDF flow within 15 seconds.
- Physical printer support/printed-QR reliability (deferred by explicit owner instruction).
- M4 physical QR/counter timing validation; M5 phone/HTTPS, encrypted backup restore
  and real end-to-end pilot dry run. M4 software is documented in M4_STATUS.md.

Use M3_GUIDE.md for the steps. Downloading or printing a PDF is not redemption.

## Owner follow-up — recorded 2026-09-28
Owner reported recognition working after cleaning the webcam, including trials with
two other people, and plans to expand the test set. Trial counts, false-match rates
and timings were not supplied. This is useful functional feedback, not M1 acceptance.
