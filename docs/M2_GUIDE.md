# M2 — local setup and walkthrough

M2 implements staff login, member/consent records, imports and events. The owner
approved building this while M1 volunteer validation is pending. Start with ID-only
registration; experimental face enrollment is now enabled in this workspace by the
owner (2026-09-27), while new configurations default to disabled. No printer or volunteers are
needed to try the member and event screens.

## Start the application

The workspace dependencies are installed. On another machine follow README.md first.
From the project root, copy .env.example to .env only if .env does not already exist.
Choose a unique database password and put the same URL-encoded password in DATABASE_URL.
Keep EVENT_AUTH_KEY_FILE outside this project. The supplied path expands to your
user's private application-data directory when the file is sourced by Bash.

```bash
cp -n .env.example .env
# Edit .env now: replace the two database password placeholders.
docker compose up -d --wait db
set -a
. ./.env
set +a
.venv/bin/alembic upgrade head
.venv/bin/event-auth-admin --username admin
npm --prefix frontend run build
.venv/bin/uvicorn event_auth.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

The administrator command asks twice for a 6–12 digit PIN without displaying it.
It creates the encryption key with private permissions and refuses to replace an
existing administrator. There is no default production PIN. On later starts, skip
the administrator command. Keep the original storage key: encrypted data cannot
be recovered without it. Encrypted backup/restore tooling is still M5 work.

Open http://127.0.0.1:8000 and sign in. If Docker reports permission denied in an
older IDE terminal, refresh your login/group membership as described in README.md.
Local development uses EVENT_AUTH_COOKIE_SECURE=false and loopback only. LAN HTTPS
and real phone access remain M5; do not use this local HTTP configuration for the pilot.

## Try members and events

1. Members → Add member. Enter details and save. This creates an ID-only member.
   Search by member ID, name or mobile; select a record to edit it.
2. Events → Create event. Add a name/date, slots and comma-separated option labels.
   Name each counter and select the options it serves; cover every option.
3. Save the event. Select a member, choose an option for each slot, then Save choices.
   Counts update immediately. Repeat for other members and mark the event ready.
4. Download counts CSV when needed. It contains slot/option codes and counts only.
5. Staff → create admin, check-in or counter accounts. Resetting a PIN invalidates
   all sessions for that account. Volunteer event-day screens arrive in M3/M4.

Event structure can be edited while DRAFT with no registrations. Once choices exist,
structure is locked to protect their meaning; create another event if the structure
was wrong. Choices can be corrected by admins in DRAFT, READY and LIVE; CLOSED
rejects changes. Starting LIVE and closing events belong to later milestones.

Deleting a member removes details, consent records, templates, thumbnail and event
registrations. M2 has no coupons yet; later coupon counts must retain only anonymous
references. Consent withdrawal removes the face templates and thumbnail while keeping
the ID-only member.

## Import without biometric consent

Download the CSV template from Import. The same headers work on the first sheet of
an .xlsx workbook. Up to 1,000 rows / 2 MB; formulas are rejected.

- Member columns: member_code, name, mobile, is_minor, plus every configured field.
  Use unique uppercase member codes, true/false for is_minor, and text-formatted
  mobile cells to preserve leading zeroes. Existing member IDs are rejected; import
  never silently overwrites existing details.
- Choices: select an event and download its template. Each row has member_code and
  one column for each slot code. Use option codes from that event's counts CSV.
  The member must already exist. Provide all slots; saving updates their choices.

Check import first, inspect row errors, then Confirm import. Validation runs again
at confirmation. Any invalid row rolls back the whole import. Import never grants
face consent or stores face data.

## Optional fake demo records

After setup, create 12 obviously fake ID-only members and an event with choices:

```bash
.venv/bin/python -m event_auth.demo --username admin
```

It asks for the admin PIN and uses the same role/audit rules. It uses DEMO-001 through
DEMO-012; a repeated run fails and rolls back rather than overwriting records.
No real names, phone numbers, images or implied consent are generated.

## Experimental face enrollment

The owner enabled experimental_face in assets/config/customer_config.json on
2026-09-27. Restart the server and refresh the browser after configuration changes.
This is a development switch, not evidence that M1 passed. Example thresholds remain
uncalibrated; do not use this to claim reliable event-day recognition.

For imported people: Members → search/select their existing record → Face registration
→ Add or replace face. Do not create a second member. Consent and capture attach to
the existing member ID; event registrations and choices remain unchanged.

Save a member first, then choose Add or replace face. Read the configured consent text,
record self/guardian consent, and only then open the camera. Minors require a guardian
name. The camera collects three good frames with quality hints and manual capture
as a backup. Review/retake before saving. Similar faces require an administrator's
explicit review; a different-person override is audited. Cancelling a replacement
does not erase the previously saved face. Only three encrypted templates and one
small encrypted reference thumbnail are retained; raw camera frames are not stored.

The persistent consent text is a draft identified as persistent-draft-v1 in config.
It differs from the temporary M1 memory-only test consent. Organizer review is still
required before the pilot. Follow FACE_TEST_GUIDE.md for M1's separate accuracy study.

## Automated checks

Use the isolated test database commands from README.md. After applying its migrations:

```bash
TEST_DATABASE_URL=postgresql+psycopg://event_auth_test:local_test_only@127.0.0.1:5433/event_auth_test env -u PYTHONPATH .venv/bin/pytest
npm --prefix frontend test
```

For the optional real Chrome smoke test, keep the isolated database running and empty,
build the frontend, then run:

```bash
TEST_DATABASE_URL=postgresql+psycopg://event_auth_test:local_test_only@127.0.0.1:5433/event_auth_test node scripts/browser_smoke.mjs
```

It uses /usr/bin/google-chrome (override CHROME_BIN if needed), fake records, a temporary
browser profile and ports 8765/9223. It refuses non-test/nonempty databases and cleans
up its own test data. Screenshots contain only fake records. Do not run it concurrently
with the PostgreSQL test suite.

## Member food defaults — approved 2026-09-30
The owner approved including every saved member automatically in each new event.
This supersedes earlier instructions to enter food choices separately for every event.
Admins set Default food option in Members; it is stored in the encrypted personal record.
New events copy that preference into each slot when its label uniquely matches an
option (ignoring case and surrounding spaces). Missing or unavailable defaults are
marked Needs choice; resolve these before marking ready or starting check-in.

Admins can override one event's choices in Events or use the Check-in shortcut before
scanning. This does not change the member default or other events. Changing a member
default affects future events only. For older events or members added later, use
Add missing members and fill missing defaults; existing selections are preserved.
Closed events cannot change. Changes do not rewrite issued coupons; use the existing
admin replacement process when necessary.

CSV/XLSX member imports accept optional default_option; old templates still work.
No migration or new dependency is needed. The reusable preferences module and
application services implement this; core rules remain unchanged. Review event
slots/options/counters before saving: automatic registrations activate the existing
structure lock immediately when members exist.
