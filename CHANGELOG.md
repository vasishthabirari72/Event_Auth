# Changelog

## Unreleased
- Added M5 admin-authenticated passphrase backup, isolated PostgreSQL restore with
  record/signature verification, read-only preflight, and a strict local HTTPS launcher.
- Added recovery/TLS tests, staff quick guides and a pilot checklist; physical camera,
  phone, timing and fresh-laptop acceptance remain pending by explicit owner direction.
- Added M4 QR redemption with server-side signature/status checks, atomic single use,
  persistent retry recovery and role-restricted lookup redemption.
- Added admin replacement/void/closure, counts dashboard and CSV. Replacement chains
  retain one entitlement; anonymous person counts survive member deletion.
- Added migration 0004, local QR camera/keyboard scanning, configurable result timing
  and sound, concurrency/rollback tests and browser retry verification.
- Added a second YuNet scale retry (240px) after reproducing a missed check-in face.
  Detection confidence and original-image quality gates remain unchanged.
- Keep check-in capture errors beside the camera and provide a temporary rejected-frame
  preview with explicit download for diagnosis; no automatic frame storage.
- Added M3 experimental event-scoped face check-in and fallback, human confirmation,
  atomic coupon issuance, server-side Ed25519 signing and repeatable QR PDF output.
  Thermal output is deferred by owner request; a generic output port supports extension.
- Reproduced webcam rejection on the owner-provided frame: scaled detection succeeds,
  but sharpness 41.22 failed the uncalibrated 60 cutoff. Experimental cutoff is now
  40; population accuracy validation remains pending.
- Added a smaller-frame YuNet retry when native-size detection finds no faces;
  restores landmarks to the original image for alignment and quality checks.
  Real webcam validation of this retry remains pending.
- Corrected capture feedback: no face detected now has its own guidance instead of
  incorrectly asking for one person. Multiple faces still block capture.
- Enabled experimental face registration for the owner’s local development workflow;
  verified imported-member identity/choices remain linked and consent gates capture.
- Added M2 staff sessions/PINs, encrypted members and consent, experimental face enrollment,
  CSV/Excel imports, event choices/counters/counts, admin UI and fake demo tooling.
- Recorded owner approval to build M2 while M1 volunteer validation remains pending.
- Reconciled approved laptop-pilot scope and nine follow-up decisions.
- Started M1 with backend/frontend skeleton, role and matching rules, migrations and checks.
- Updated agent prompts for approved M1–M5 milestones, model choice and follow-up decisions.
- Verified Docker/PostgreSQL, applied the test baseline migration, and enabled the database integration check.
- Added separate face calibration/validation, unknown-person checks, aggregate reports and synthetic scale benchmarks.
