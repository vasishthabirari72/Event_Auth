# M2 status — 2026-09-27

Implementation available; owner-reported timing targets pass. Population face accuracy
and the remaining pilot hardware/privacy acceptance checks remain NOT VERIFIED.
Owner approved starting M2 while M1 volunteer validation is pending.
M1 is not marked complete. Owner has authorized M3 with PDF output.

## Implemented

- Staff usernames + 6–12 digit PINs, salted scrypt hashes, persistent attempt limits,
  random server sessions, HttpOnly/SameSite cookies, origin/CSRF checks, expiry/logout
  and admin PIN resets that revoke sessions.
- Administration permissions enforced by the service entry point and core role policy;
  counter/check-in roles cannot read or mutate member/face/config/staff/event records.
- Versioned PostgreSQL migration 0002: staff, sessions, login limits, members, consents,
  face templates, events, generic slots/options/counters, registrations/selections and audit.
- Config-driven member forms, ID/name/mobile search in POST bodies, optimistic edits,
  ID-only registration, guardian consent, withdrawal and full member deletion.
- Encrypted personal payloads, guardian details, templates and a cropped reference photo;
  encryption key kept outside the database/project. Wrong recovery key fails startup.
- Consent-before-camera, three good frames with automatic/manual capture, quality hints,
  retake and duplicate admin review. The owner enabled experimental enrollment in the
  workspace on 2026-09-27; the schema default for new configurations remains off.
- CSV/.xlsx preview and atomic import of member details or event choices. Invalid rows
  roll back the complete import; formulas/oversized files are rejected; no implicit consent.
- Event setup, slots/options, up to two counters, member choices, counts-only CSV and
  DRAFT → READY. Admin choice changes allowed until CLOSED. Structural edits lock
  once registrations exist. LIVE/CLOSED transitions are later milestone work.
- Localized admin screens, accessible controls, validated branding/fields, fake demo
  command and operator guide. No runtime internet service or new frontend dependency.

## Shared core change reason

Added generic consent/guardian, PIN format, closed-event and per-slot choice rules.
These serve every deployment, contain no customer/food-specific behavior, and import
only the standard library. Persistence/crypto/model execution stay outside core and
are injected into services. Existing face/role behavior is preserved.

## Verification evidence

- 94 backend tests passed against the isolated PostgreSQL database, none skipped;
  100% coverage of the current core (98 statements).
- Role bypass, session revocation, rate limits, wrong-key/tamper rejection, encrypted
  payloads, consent/guardian/withdrawal, duplicate override, full deletion and ID-only paths.
- Import preview/rollback, CSV/Excel, formula rejection, counts, event locking and closed
  event rules. Concurrent duplicate registration has one winner. Audit commit failure
  rolls back the member and returns failure before an HTTP success response.
- Six frontend transport/status tests pass. Formatting, lint, types and production build pass.
- Real headless Chrome smoke test: login, config-driven ID-only registration, event
  setup, choices, READY, staff creation, logout and volunteer access boundary.
- Desktop and 390-pixel responsive browser checks passed without horizontal overflow.
  Screenshots: screenshots/m2-members.png and screenshots/m2-members-mobile.png
  (fake data only; browser emulation is not a physical phone test).
- Migration 0002 successfully downgraded to 0001 and reapplied on the empty isolated
  database; Alembic check found no schema drift. Test database stopped after validation.
- CLI help checks for administrator setup and fake demo creation.
- 2026-09-27: imported-member enrollment preserves the existing UUID, readable member
  code and all event choices; consent is still required. Tested with a fake face adapter.
- Enabled Face registration section and consent-before-camera control verified in Chrome.
  Local SFace/YuNet hashes checked and both real models loaded without capturing faces.
- Local app restarted with its existing environment to load the enabled configuration;
  database readiness passed. Real camera/accuracy validation still requires the owner.
- Two pre-existing deprecation warnings remain: Starlette HTTPX and Alembic path_separator.
- CI workflow exists but was not executed on a hosted runner.

## Acceptance still pending

| Criterion | Status |
|---|---|
| Service permissions, encryption, migration, consent, import and deletion checks | PASS — automated evidence above |
| Face enrollment within 90 seconds | PASS — owner reported successful capture within target on 2026-09-27 |
| Event setup with choices within five minutes by an operator | PASS — owner reported completion within target on 2026-09-27 |

Latest owner report (2026-09-27): face registration now completes on the laptop.
The reported camera frame reproduced a sharpness rejection at 41.22 against the
initial cutoff of 60. A provisional cutoff of 40 accepts that frame; a deliberately
blurred version is rejected. Detection includes a smaller-frame retry with restored
landmarks. This is not recognition calibration or population accuracy evidence.
The supplied debug image was moved outside the source tree to /tmp/face-debug.jpg.
Owner subsequently confirmed registration <=90 seconds and event setup <=5 minutes.
Real duplicate accuracy remains unverified.
| Real duplicate-face detection quality and chosen thresholds | NOT VERIFIED — M1 calibration/validation pending |
| Physical laptop camera, phone and printer checks | NOT VERIFIED — phone/printer remain later milestones |
| Consent wording reviewed for pilot; encrypted backup restore | NOT VERIFIED — required before pilot |

Use M2_GUIDE.md to initialize the real local database and choose the first admin PIN.
Only the isolated test database was initialized by the coding agent; no production
administrator, real member data or default production credentials were created.
