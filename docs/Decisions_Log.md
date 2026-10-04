# Decisions Log

> Answers to the 22 questions raised by the agent after reading the docs. Applies to the current build defined in `Demo_Scope.md` (local laptop server, FastAPI + PostgreSQL + React). Where this file and older docs conflict, this file and `Demo_Scope.md` win.

| # | Question | Decision |
|---|---|---|
| 1 | Docs folder name | Use lowercase `docs/`. |
| 2 | Registration once or per event? | Members register once and are reused across events. Food choice is collected per event. |
| 3 | Pilot topology | 1 check-in desk, up to 2 food counters. |
| 4 | Per person or household coupons? | Strictly one coupon per person per slot. Households are later. |
| 5 | Android only? | No native app for now. Phones and tablets use the browser. |
| 6 | Language and pilot community | English only for now, with all UI text in translation files. Pilot community not decided; don't block on it. |
| 7 | Disconnected counters and double redemption | The server makes every redemption decision. If a counter loses connection, it pauses and shows "Reconnecting - send to admin desk". |
| 8 | Standalone counter phone | Not used. Every counter works through the server, so voids, reprints and event status are always current. |
| 9 | "No network" vs hotspot | "Offline" means no internet required. Local Wi-Fi between devices and the laptop is required. |
| 10 | Issue before or after printing? | Save the coupon as ISSUED before printing, with `print_count` and `last_printed_at`. A retried print uses the same coupon code. Admin reprint voids the old coupon and issues a new one in one transaction. |
| 11 | Event closure and expiry | Add an EXPIRED state. Closing an event expires all remaining ISSUED coupons in one transaction. |
| 12 | Generic core vs meal_slots | Core uses generic entitlement slots and options. Meal and food wording comes from config. |
| 13 | Core imports and platform dependencies | Core never imports the web framework, database driver, config loader or UI. Platform services (face model runtime, printer, storage) sit behind interfaces and are injected. |
| 14 | Fallback and roles arrive too late | Role checks live in the core service layer from the start. PIN login in M2, fallback search in M3. |
| 15 | Who can change selections | Only admins, at any event status. |
| 16 | What data moves between devices; reports | Devices receive only what their screen needs (the counter sees coupon status, member name, food choice). Never send face templates, reference photos or mobile numbers to counter devices. CSV export contains counts only. |
| 17 | Consent fields, retention, deletion | Store purpose, `consent_text_version` and date with each consent. Deleting a member deletes their face data and reference photo. Audit logs store IDs only. Agent drafts plain-English consent text as a template; owner gets it reviewed before the pilot. Retention and restored-backup rules are later. |
| 18 | Security policies | For now: PIN login, admin can reset staff PINs, Ed25519 signing key stored on the server only. Agent writes a short `docs/SECURITY.md` covering these plus LAN HTTPS setup. Pairing, licensing and key rotation are later. |
| 19 | Benchmark size | Test identify speed with 300 members for the pilot, plus a scale check at 2,000 members with 3 templates each (6,000 templates). |
| 20 | Model, printer, test phones | Nothing selected yet. In M1, the agent proposes 2-3 ONNX face models with licences; owner chooses one that allows commercial use. Owner buys a printer before M3. Phones are only needed at M5. |
| 21 | MEDIUM-confidence actions; counts on volunteer screens | MEDIUM shows Yes and No only; No leads to search. The check-in screen may show a single "Checked in: N" count. Full dashboard is admin only. |
| 22 | Modules for the pilot | Food coupons and Excel/CSV import only. |

## Later changes

| Date | Change |
|---|---|
| — | Database: PostgreSQL instead of SQLite, running locally via Docker. Tests use a separate test database. Pilot backup contains `pg_dump` plus recovery keys in a passphrase-encrypted archive; restore must be tested. |

## Confirmed follow-up decisions — 2026-09-24

These nine decisions were explicitly approved by the owner, one by one.
1. New documents override only explicit changes. All other original core-protection,
   accessibility, testing and privacy rules remain in force.
2. Admins may redeem an issued coupon by lookup if printing fails, through the same
   atomic one-time redemption checks.
3. Record guardian consent for under-18s before face capture. Deletion removes all
   member personal details, templates and photos; coupon counts retain anonymised references.
4. Pilot backup is a passphrase-encrypted archive of the database and recovery keys.
   A successful restore test is required before the pilot; no backup UI required yet.
5. Face acceptance: zero HIGH false matches in the consented test set; at least 90%
   genuine attempts in HIGH/MEDIUM in normal indoor lighting; identify within 1 second
   for 300 members on the pilot laptop. Benchmark 2,000 members / 6,000 templates and
   record results, but do not make that scale a pilot blocker.
6. Lost-response retries retrieve the original redemption result without another
   redemption. Coordinate redemption, reprint and closure and test their races.
7. Audit issuance, redemption, selection changes, imports and staff PIN resets, as well
   as existing sensitive actions. Record actor ID, time and relevant record IDs; never
   names, phone numbers, PINs or face data.
8. Expired coupons show red “EXPIRED — DO NOT SERVE”. Event closure is final for the pilot.
9. Python/FastAPI and React/TypeScript replace Flutter standards. Retain independent
   core logic, migrations, formatting, linting, type checks, automated tests and at least
   80% core coverage. Validate on laptop during development; phones and printer before pilot.

## Model decision — 2026-09-24
Owner selected the free SFace + YuNet models for M1 evaluation. See MODEL_EVALUATION.md.

## Milestone sequencing — 2026-09-25
Owner approved continuing to M2 while volunteers are unavailable. M1 remains
validation pending; face recognition remains experimental until its acceptance tests
pass. Build login, member/consent workflows, imports and events independently. This
explicitly overrides the M1-before-M2 gate, not accuracy or pilot acceptance criteria.

## Experimental enrollment — 2026-09-27
Owner approved enabling and testing face registration as the next M2 step. Enable it
in the workspace configuration, preserving consent/guardian checks and ID-only fallback.
Imported members receive faces on their existing IDs; event choices stay linked.
This does not authorize claiming face accuracy acceptance or advancing to M3.

## M3 and PDF output — 2026-09-27
Owner confirmed both M2 timing targets (registration <=90 seconds, event setup <=5 minutes)
in conversation; these are owner-reported measurements, not an automated usability result.
Owner explicitly requested M3, replacing thermal output for now with a signed QR coupon
PDF and retaining an adapter boundary for different printer types later. No physical
printer integration or printer acceptance claim in this increment. Face identification
remains experimental while M1 volunteer calibration/accuracy validation is pending.
Human confirmation, event-scoped matching and single issuance remain mandatory.

## M4 development continuation — 2026-09-28
After reporting successful recognition with two people following camera cleaning, the
owner asked to continue. Proceed with the next planned milestone, M4 development;
this does not certify M1 accuracy, M3 timing or pilot readiness. Preserve signed PDF
output and the deferred physical-printer integration. Larger consented evaluation,
real counter-device timing and M5 readiness checks remain required.

## M5 preparation with deferred camera testing — 2026-09-28
Owner explicitly deferred camera testing and asked for the next step. Proceed with M5
recovery tooling, HTTPS preparation, local verification and operating guides. Camera,
phone, timing, fresh-laptop and 20-person dry-run acceptance remain pending; do not
claim pilot readiness. PDF output and the deferred thermal integration remain unchanged.

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

## Free online demo — 2026-10-04
Owner requested online hosting, selected free hosting, authenticated Neon and
explicitly linked project misty-meadow-56509941 production with an empty neon.ts.
Proceed with Render Free plus a fresh Neon database for the online demo. Preserve
the offline laptop deployment. No migration of real member or face data is authorized
or performed. Free-host face performance and online acceptance remain unverified.
