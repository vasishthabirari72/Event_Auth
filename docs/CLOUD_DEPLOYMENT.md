# Free online demo deployment (in preparation)

Owner requested free online hosting on 2026-10-04 and reported signing in to
Render and Neon. This extends the earlier cloud-out-of-scope decision for an online
demo; the existing local server remains the offline event option. Use a fresh Neon
database and dedicated cloud keys, not the laptop's real data or keys.

1. Create a Neon Free project named event-auth-demo. Choose PostgreSQL 17 and a
   region near the Render service. Keep its direct connection URL private.
2. Prepare the empty database from your laptop: enter the direct Neon URL privately
   into DATABASE_URL, replacing the initial postgresql:// with postgresql+psycopg://.
   Keep sslmode=require. Run `.venv/bin/alembic upgrade head`.
3. Set EVENT_AUTH_KEY_FILE to a new private location outside the repository, e.g.
   ~/.local/share/event-auth-cloud/storage.key. Run
   `.venv/bin/event-auth-admin --username admin` and choose a new PIN interactively.
   This creates the cloud administrator and storage key. Do not source the local
   .env while running these cloud steps.
4. Generate a dedicated signing key with
   `.venv/bin/python -m event_auth.adapters.signing ~/.local/share/event-auth-cloud/coupon-signing.key`.
5. In Render create a Free Web Service from Event_Auth, runtime Docker, branch main,
   root directory blank, Dockerfile ./Dockerfile, health check /api/ready.
6. Set DATABASE_URL to the same Neon SQLAlchemy URL, retaining TLS parameters.
   Add secret file storage.key containing the cloud storage key's text; add secret
   file coupon-signing.b64 containing the base64 encoding of the cloud signing key.
   Render accepts text secret files; cloud_start.sh decodes the signing key and
   sets private permissions. Keep both keys unchanged across restarts/redeploys.
7. Deploy only after these deployment files are pushed. Confirm /api/ready, login,
   fake member creation, event setup and PDF generation, then test face recognition
   performance. Redeploy and verify records and coupons still work.

The Docker build provisions verified models in advance. Runtime uses one worker,
HTTPS cookies, the exact Render hostname/origin and no access logs. The app serves
both React and FastAPI from the same origin. No real laptop records are uploaded.

Render Free sleeps when idle; memory/CPU and face performance need validation.
No production or offline-event reliability claim is made for this free deployment.
Cloud backups need a separate operator procedure; local Docker backup tooling is
not automatically configured for Neon. Hosted deployment has not yet been tested.

Provider documentation:
- https://render.com/docs/docker
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/free

## Setup progress — 2026-10-04
Linked project misty-meadow-56509941, branch production. Verified its public schema
was empty, applied migrations through 0004 and created a dedicated cloud admin.
The local database was not changed. Separate cloud credentials are stored privately
outside the repository in ~/.local/share/event-auth-cloud/:
- render-database-url.txt: direct SQLAlchemy/TLS database URL for Render DATABASE_URL.
- storage.key: contents for Render secret file storage.key.
- coupon-signing.b64: contents for Render secret file coupon-signing.b64.
- admin-login.txt: initial website login, for the owner only.

The root neon.ts contains the requested empty policy. It configures Postgres only;
it does not host this Python app. .env.neon and .neon are ignored by Git.

Local image verification completed: Docker build succeeded; under a 512 MiB cap,
UI and readiness returned 200, the dedicated admin could log in with a Secure cookie,
and authenticated members returned an empty list. Both real face models loaded.
This verifies packaging/startup, not recognition speed or Render-hosted acceptance.
Do not repeat the initialization steps above: the database and administrator already exist.
Next: deploy the committed Docker image source in Render with the private files above.
