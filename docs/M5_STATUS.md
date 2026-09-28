# M5 status — 2026-09-28

Local preparation implemented. Owner explicitly deferred camera testing and authorized
continuing to M5. This is not pilot readiness or a waiver of physical acceptance.
Thermal printer integration remains deferred; coupons are signed PDFs.

## Implemented
- Admin-authenticated CLI backup with existing persistent PIN throttling and ID-only
  audits. Consistent PostgreSQL snapshot, keys/config/model metadata inside a
  passphrase-encrypted authenticated archive; no plaintext dump on disk.
- Separate recovery PostgreSQL service on loopback port 5434 with its own persistent
  volume. Restore cannot address the live service, refuses occupied targets, verifies
  counts/decryption/coupon signatures and leaves the recovered app offline.
- Recovered sessions and short-lived check-in tickets are excluded. Used coupon states
  and request receipts survive: retry recovery cannot create a second serving instruction.
- Read-only preflight for config, model hashes, UI build, schema, keys and encrypted records.
- HTTPS launcher with certificate/key/SAN/expiry checks, specific private-IP binding,
  secure cookies, exact host/origin and no proxy-header trust/access logs.
- M5_GUIDE.md, STAFF_GUIDES.md and PILOT_CHECKLIST.md; CI now provisions isolated
  test/recovery services and runs the recovery test instead of skipping it.
- No new Python/frontend dependencies or core rule changes. mkcert/libnss3-tools are
  optional later certificate-setup tools; no installation/trust-store changes performed.

## Evidence
- 136 backend tests passed, none skipped, on isolated PostgreSQL test/recovery services.
  100% core coverage (126 statements). Ruff format/lint and mypy pass (50 source files).
- Real pg_dump/pg_restore round trip with obviously fake encrypted personal data,
  guardian/consent data, thumbnail, three synthetic templates and a redeemed signed coupon.
  Recovered keys decrypt records; signatures verify; counts match; replay returns
  RECOVERED, new scan returns ALREADY USED. No real face capture was involved.
- Wrong passphrase/tampering/truncation/path contents rejected; private exclusive files;
  wrong/live/remote restore targets rejected. Invalid PostgreSQL archive leaves the
  isolated target empty. An occupied target is refused without overwriting it.
- Real local TLS connection using an ephemeral test certificate with certificate
  verification enabled: login, Secure/HttpOnly/SameSite cookies, unauthenticated rejection,
  foreign Host/Origin rejection. Wrong SAN/private-key permissions/bind address rejected.
- Live read-only preflight passed using the existing original keys and records. No real
  backup was created, no real coupon redeemed, and no live event closed by these tests.
- Existing Starlette HTTPX and Alembic path_separator deprecation warnings remain.
- This change adds operational tools; the existing M4 frontend was not changed.

## Still pending
- Camera/QR tests deferred by the owner; formal M1 face accuracy and timings still pending.
- Certificate trust setup and camera permissions on actual phones; venue Wi-Fi and
  physical two-counter operation, scanner speed, disconnected behavior and service restart.
- Actual fresh-laptop setup and a 20-person end-to-end dry run; <10-minute committee demo.
- Owner's real encrypted backup and recovery-drive drill. Automated restore used fake data;
  old-backup deletion/retention and reconciliation procedures require owner review.
- Owner review of consent wording. Physical thermal acceptance resumes only when requested.

The current app remains localhost-only. M5 tooling is ready for the remaining operator
and physical checks; M5 acceptance is not complete.
