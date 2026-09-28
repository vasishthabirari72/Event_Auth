# M5 — setup, recovery and pilot preparation

Camera testing is deferred at the owner's request. These tools prepare the pilot;
they do not certify face accuracy, phone compatibility or the 20-person dry run.
The existing app continues at http://127.0.0.1:8000. Signed PDFs remain the approved
output; thermal printer support is deferred.

## Readiness check
From the project root, load the existing local environment without printing it:

```sh
set -a
. ./.env
set +a
.venv/bin/python -m event_auth.operations.preflight
```

This reads configuration, model hashes, the frontend build, schema and original keys,
and checks decryption and coupon signatures without changing member/coupon records.
It prints only statuses. Start `docker compose up -d --wait db` if the database is stopped.
No new Python or frontend package is required. PostgreSQL tools run inside the existing
PostgreSQL 17 Docker image; host `pg_dump` is not needed. Docker must work for your user.

## Encrypted backup
Use your administrator username and choose a unique passphrase of at least 12 characters.
The CLI prompts without echoing PIN/passphrase; neither is a command-line argument.
The destination directory must already exist. The file must not exist.

```sh
mkdir -p backups
.venv/bin/python -m event_auth.operations.recovery backup \
  --username admin --output backups/event-backup.eab
```

The encrypted archive includes a consistent PostgreSQL dump, the original storage and
coupon-signing keys, customer config, model manifest and thresholds. It excludes active
sessions, login throttles and short-lived check-in tickets. Persistent redemption receipts
are included. Database credentials and the HTTPS CA private key are not included.

Store the `.eab` file on your chosen backup drive and keep its passphrase separately.
Do not copy loose recovery keys or plaintext dumps to USB. Back up before the event and
after closing it. A backup cannot include transactions committed after its snapshot;
restoring an older copy during an active event needs reconciliation before serving resumes.
Never run both the original and restored database as competing event authorities.

The archive uses Scrypt (N=131072, r=8, p=1), a fresh salt and AES-256-GCM with a fresh
nonce; headers are authenticated. The archive is limited to 256 MiB, and dump/bundle
processing uses memory. This is a laptop-pilot tool, not a streaming large-database backup.
Encrypted files use exclusive creation and mode 0600. No plaintext dump is written to disk.

## Isolated restore drill
Only restore your own trusted backup. The restore command cannot target the live `db`
service and refuses a nonempty recovery database or an existing output directory.
It does not start a recovered serving app.

Choose a new database password at the hidden prompt. The recovery service uses port
5434, distinct from live 5432 and tests 5433. Its named volume persists across stops.

```sh
read -r -s -p 'Recovery database password (letters/numbers): ' RESTORE_POSTGRES_PASSWORD
export RESTORE_POSTGRES_PASSWORD
export RESTORE_DATABASE_URL="postgresql+psycopg://event_auth_restore:${RESTORE_POSTGRES_PASSWORD}@127.0.0.1:5434/event_auth_restore"
docker compose --profile recovery up -d --wait restore-db
.venv/bin/python -m event_auth.operations.recovery restore \
  --archive backups/event-backup.eab \
  --directory "$HOME/event-auth-recovery"
```

Use letters/numbers for that example URL, or URL-encode other password characters.
The database password protects the recovery service; it is separate from the archive
passphrase. An already-created recovery volume retains its original database password.

A successful restore writes private key/config files and `verified.json` in the new
0700 directory. Verification compares table counts, decrypts stored personal/face/coupon
records and verifies existing coupon signatures. Staff must log in again. The recovered
database retains used/voided/expired states and request receipts. Restore failures never
automatically wipe data; keep the recovery service offline until investigated. A failed
attempt may leave its private directory or an unverified recovery database; do not treat
it as successful without `verified.json` and the success message.

Stop the drill service afterward:

```sh
docker compose --profile recovery stop restore-db
```

For disaster recovery, first stop the old event authority and review transactions and
member deletions since the snapshot. On the recovery machine, use the original app build,
recovered `storage.key`, `signing.key` and `config.json`, and the recovery database URL.
Provision model weights matching the saved `models.json`; compare/copy the saved
`thresholds.json` to `assets/models/thresholds.example.json` before enabling recognition.
Do not bootstrap new keys or a new admin over recovered data. Run preflight and verify
counts/coupons before explicitly switching devices to the recovered server. Recreate TLS
certificates for its reserved address. Reapply post-backup deletion requests before use;
long-term retention/restored-backup policy still needs owner review.

## Local Wi-Fi HTTPS — when phones are available
Reserve a private IPv4 address for the laptop on the event router. Keep laptop and
phones on the same private network; disable client isolation where necessary. Internet
is not needed after provisioning. Do not forward the port to the internet.

Install `mkcert` and Ubuntu `libnss3-tools` using the [upstream setup instructions](https://github.com/FiloSottile/mkcert#installation).
These are certificate-setup tools, not running-app dependencies. `mkcert` is intended for
local development; use this guide for controlled pilot devices, not public production
certificate management. Neither installation nor trust-store changes were performed here.

Replace the example IP with the laptop's reserved address before running:

```sh
EVENT_AUTH_LAN_IP=192.168.1.50
EVENT_AUTH_TLS_DIR="$HOME/.local/share/event-auth/tls"
mkdir -p "$EVENT_AUTH_TLS_DIR"
chmod 700 "$EVENT_AUTH_TLS_DIR"
mkcert -install
mkcert -cert-file "$EVENT_AUTH_TLS_DIR/server.pem" \
  -key-file "$EVENT_AUTH_TLS_DIR/server.key" "$EVENT_AUTH_LAN_IP"
chmod 600 "$EVENT_AUTH_TLS_DIR/server.key"
.venv/bin/python -m event_auth.operations.lan \
  --host "$EVENT_AUTH_LAN_IP" --cert "$EVENT_AUTH_TLS_DIR/server.pem" \
  --key "$EVENT_AUTH_TLS_DIR/server.key" --check
```

After loading `.env`, run the same command without `--check` to serve HTTPS on port 8443.
The launcher binds only the selected IP, checks certificate/key/SAN/expiry, forces secure
cookies and exact host/origin restrictions, and disables access logs and proxy-header trust.
If a firewall is enabled, permit TCP 8443 only from the event subnet; keep PostgreSQL
loopback-only. Use the same HTTPS address on every device and sign in again.

Install only `rootCA.pem` from `mkcert -CAROOT` on intended phones, using the device's
certificate settings. Never distribute `rootCA-key.pem`. Confirm that the browser trusts
the certificate without a bypass before testing camera access. Device-specific trust and
permissions must be tested on the actual phones. See [upstream mobile trust notes](https://github.com/FiloSottile/mkcert#mobile-devices).

## Fresh-laptop setup and pilot gate
Follow README's fresh-machine setup, provision the original approved models, create the
first administrator and signing key only for a new installation, build the UI, then run
preflight. Complete dependency/image downloads before disconnecting the internet.
For a recovered installation, use the restore instructions instead of bootstrap commands.
A separate fresh-laptop installation has not yet been tested.

Use STAFF_GUIDES.md for the two-minute volunteer introduction and PILOT_CHECKLIST.md
for the pending acceptance record. No camera or physical-device test is implied by
successful automated tests or preflight.

## Recovery format references
The implementation uses existing [cryptography authenticated-encryption primitives](https://cryptography.io/en/latest/hazmat/primitives/aead/)
and [Scrypt](https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#scrypt).
A PostgreSQL [exported snapshot dump](https://www.postgresql.org/docs/17/app-pgdump.html)
keeps counts consistent; [single-transaction restore](https://www.postgresql.org/docs/17/app-pgrestore.html)
avoids committing a partial SQL restore when PostgreSQL reports an error.
