# Security plan and current status

## M2 status
Authenticated administration is implemented; bind to 127.0.0.1 during development.
Face lab remains a separate consented memory-only tool. Persistent face enrollment
is experimental; new configurations default to disabled. The owner explicitly enabled
it in this workspace on 2026-09-27. All consent and role restrictions remain enforced.
This is not pilot/LAN readiness; M1 volunteer acceptance and M5 HTTPS remain pending.

Implemented controls:
- PINs use salted scrypt (N=16384, r=8, p=1); 6–12 ASCII digits. Persistent account
  and peer attempt buckets allow five failures per five-minute window across workers.
- Random 256-bit session tokens; only hashes in PostgreSQL; absolute eight-hour expiry.
  HttpOnly, SameSite=Strict cookies; CSRF token on mutations and explicit allowed origins.
  Logout/PIN reset revoke sessions. Secure cookies are the default; the .env example
  disables Secure only for localhost development, which rejects non-loopback hosts.
- Every M2 operation enters the admin service, which checks the core role policy.
  Counter/check-in roles cannot request member lists, photos, templates or phone data.
- Fernet authenticates/encrypts member details, guardian details, templates and thumbnail.
  Key file is private (0600), outside PostgreSQL/project; startup checks an existing
  member against it. Metadata/IDs/event definitions are not whole-database encryption.
- Consent precedes capture; minors require guardian consent. Withdrawal removes
  templates/thumbnail. Deletion cascades all member personal records and registrations;
  audit entries retain IDs only. Coupon snapshots/reasons and member links are also
  removed; anonymous entitlement and person counts remain.
- Sensitive writes and audits share one transaction, committed before HTTP success.
  Database errors hide bind parameters; HTTP validation errors do not echo inputs.
  Search terms travel in POST bodies. Run with --no-access-log; no request-body logging.
- Imports are bounded and validated, with safe XML parsing and no formulas. Preview
  persists nothing; confirmation revalidates and rolls back all rows on any error.
- Model files are local and hash-verified before experimental enrollment. No raw camera
  images are stored; only three versioned encrypted vectors and one cropped thumbnail.
  Duplicate enrollment reviews are serialized and overrides audited.
- The bootstrap command has no shipped/default administrator or PIN. Recovery-key
  backups and a successful encrypted restore remain mandatory M5 work.

## Required before pilot
- PIN login identifies staff; hash PINs with a suitable password KDF, rate-limit attempts,
  use server sessions and service-layer role checks. Admins may reset staff PINs; audit resets.
- Ed25519 signing key stays on server, never sent to browsers or source control.
- Encrypt stored embeddings/reference thumbnails; keep recovery keys outside the database
  and source tree with restrictive permissions. No names/phones/biometrics in logs.
- Counter responses contain only necessary coupon status/name/choice. No photos/templates/mobile.
- Server transaction is sole redemption authority. Disconnected counters pause. Persist
  idempotency results scoped to actor/action/request; reject key reuse with changed payload.
  Replayed confirmations must not be presented as a new instruction to serve.
- Coordinate issue/reprint/redeem/close with database transactions; no reopening CLOSED events.
- Passphrase-encrypted archive includes pg_dump and recovery keys; never leave plain USB dumps.
  Restore to a separate environment and verify decryptability before pilot. Retention and
  deletion after restoring older backups remain policy work, not a claim of completion.

## LAN HTTPS setup (M5; not yet validated)
Provision the laptop and dependencies before arriving at the event. Use a private local
router/hotspot with a stable server address. Generate a local CA and certificate for
that address using mkcert; install only the CA certificate on intended client devices.
Never distribute the CA private key. Serve the production UI and API from the same HTTPS
origin; restrict allowed hosts/origins and firewall access to the event network.
Confirm camera access on each supported phone browser and test with internet disconnected.
Do not enable permissive CORS or disable browser certificate checks to make cameras work.

## M3 implemented controls
- Admin/check-in services enforce CHECK_IN permission; counters cannot search members,
  retrieve reference photos, issue coupons or download PDFs. Admin alone starts READY events.
- Event/slot eligibility and non-withdrawn, current-version face consent restrict candidates.
  The UI requires an explicit consent confirmation before opening the check-in camera.
  Unknown/unregistered people use fallback/admin registration; captures are memory-only.
- Actor-bound five-minute tickets separate match/lookup from explicit human confirmation.
  Confirmation rechecks event status, selection and face consent. Same-ticket retries return
  the original coupon. A current-coupon partial unique index plus service history checks prevent repeat
  issuance even after use; only explicit admin replacement can supersede a void coupon.
- Event -> member -> ticket/coupon locking coordinates concurrent operations and deletion.
- Ed25519 keys live only in a private 0600 server file, provisioned explicitly once. Include
  this file with recovery keys in the required encrypted pilot backup; never overwrite it.
- Snapshots (name, member code and signed QR included) use Vault encryption. PDFs are rendered
  in memory after issuance commits, then sent through authenticated CSRF-protected requests.
  No server PDF archive. Deletion clears all snapshot ciphertext and removes the member link;
  anonymous slot/option counts remain. Already-downloaded PDFs cannot be recalled.
- `print_count` counts successful server PDF renders; `last_printed_at` records their time.
  Neither proves a download reached the browser nor a physical print. Failed rendering rolls
  back that render's counter/audit, while the earlier issued coupon remains available to retry.
- A PDF alone is not proof of eligibility to serve: the counter validates current server state.

## M4 implemented controls
- Server verifies Ed25519 signature, stored coupon scope, event/slot, status and counter
  option before atomic redemption. QR decoding uses local OpenCV; no remote service.
- Event/member/coupon locks coordinate redemption, replacement, closure and deletion.
  Status changes, ID-only audits and operation receipts commit in one transaction.
- Receipts are scoped to actor/action/request UUID with a canonical-payload hash. Raw
  QR payloads and personal details are not stored in receipts. Changed-payload reuse
  is rejected. Retries return RECOVERED, never a new green SERVE instruction.
- Connection uncertainty keeps the original request for retry and prevents another scan.
  Refreshing loses that browser retry context; ask the admin to inspect server status,
  never infer permission to serve from a local image or an unavailable response.
- Admin replacement voids the old coupon and creates one signed replacement atomically;
  redeemed entitlements cannot be replaced. Reasons are encrypted. Closure is final and
  expires outstanding coupons. Lookup redemption uses the same single-use service.
- Counter responses exclude photos, templates and mobile numbers. Counts exports contain
  validated slot/option codes and aggregate numbers only. Member deletion removes coupon
  snapshots/reasons and member links, retaining anonymous event-person and claim tokens.
- Existing signing/encryption keys must be preserved during upgrades. Migration 0004
  backfills anonymous IDs without changing existing coupon codes/signatures.

## M5 recovery and HTTPS tooling
Backup CLI requires an administrator PIN using persistent login throttling and leaves no
CLI session. Backup-start/completion and restore are audited with IDs only. A shared
PostgreSQL snapshot supplies dump and verification counts. Keys/config are inside the
Scrypt/AES-256-GCM authenticated archive; no plaintext dump file is written. Archives
and recovered keys use exclusive 0600 files; recovery directory is 0700. Sessions, login
buckets and confirmation tickets are excluded; operation receipts persist.
Restore authenticates the archive before writing, targets only the separate loopback
recovery service, refuses occupied databases and verifies counts/decryption/signatures.
It does not launch an app or replace live data. Preserve only encrypted archives on USB.
Keys remain private server files when recovered. See M5_GUIDE.md for snapshot-age,
post-backup deletion and single-authority recovery procedures.

The HTTPS launcher checks key permissions, matching IP SAN and validity; permits only
a specific private IPv4 bind; forces secure cookies/exact host and origin and disables
proxy-header trust/access logs. Certificate trust setup is manual; no trust-store changes
or LAN listener were enabled. Local TLS transport is tested; phone trust and physical
camera/network acceptance are pending. Existing localhost development remains available.
