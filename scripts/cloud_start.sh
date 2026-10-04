#!/bin/sh
set -eu
# Render secret files survive redeploys; private runtime copies enforce key permissions.
umask 077
mkdir -p /tmp/event-auth-keys
cp /etc/secrets/storage.key /tmp/event-auth-keys/storage.key
base64 -d /etc/secrets/coupon-signing.b64 > /tmp/event-auth-keys/coupon-signing.key
chmod 600 /tmp/event-auth-keys/*.key
export EVENT_AUTH_KEY_FILE=/tmp/event-auth-keys/storage.key
export EVENT_AUTH_SIGNING_KEY_FILE=/tmp/event-auth-keys/coupon-signing.key
: "${DATABASE_URL:?Set the Neon SQLAlchemy connection URL}"
: "${RENDER_EXTERNAL_HOSTNAME:?Render hostname is required}"
export EVENT_AUTH_HOSTS="$RENDER_EXTERNAL_HOSTNAME"
export EVENT_AUTH_ORIGINS="https://$RENDER_EXTERNAL_HOSTNAME"
export EVENT_AUTH_COOKIE_SECURE=true
alembic upgrade head
exec uvicorn event_auth.api.app:app --host 0.0.0.0 --port "${PORT:-10000}" --workers 1 --no-access-log
