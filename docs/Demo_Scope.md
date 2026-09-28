# Demo Scope (Local Laptop Version)

> **This file is the source of truth for the current build.** Where it conflicts with the other docs, this file wins. Only explicit changes override the original documents. All other core-protection, accessibility, testing and privacy rules remain in force. The confirmed follow-up decisions in `Decisions_Log.md` apply.

---

> Owner update (2026-09-27): M3 currently produces a signed QR coupon PDF. Thermal
> printer integration and physical print acceptance are deferred; retain output adapters
> for future printer types. Face accuracy acceptance remains pending.

## 1. Goal

Build a working version that:
1. Can be **demoed live** to community committees on one laptop in under 10 minutes.
2. Can run **one real pilot event** (up to ~300 members, 1 check-in desk, up to 2 food counters).

We have no customers yet. Speed of learning matters more than completeness.

## 2. Setup

```
                 Local Wi-Fi (router or laptop hotspot, no internet needed)
                                        |
   +------------------+     +-----------+-----------+     +------------------+
   | Check-in device  |     |   LAPTOP (server)     |     | Counter device(s)|
   | phone/tablet     |<--->|  FastAPI + PostgreSQL |<--->| phone + browser  |
   | browser + camera |     |  React UI (served)    |     | or USB scanner   |
   +------------------+     |  Face engine (ONNX)   |     +------------------+
                            |  Thermal printer (USB/network)
                            +-----------------------+
```

- During development and demos: everything runs on the laptop, using the laptop webcam. No phones needed.
- At the pilot: phones/tablets open the app in a browser over local Wi-Fi. HTTPS with a locally trusted certificate is required so phone browsers allow camera access.
- The server makes every decision. There is no phone-to-phone sync.

## 3. Stack

| Part | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Database | PostgreSQL, running locally on the laptop (installed or via Docker), via SQLAlchemy + Alembic migrations. Same database for cloud later |
| Frontend | React (Vite), served by the backend |
| Face detection + embedding | ONNX models run on the laptop CPU. **Model licence must allow commercial use**; agent proposes options, owner chooses |
| QR | Signed payload (Ed25519), generated on server; scanned in browser or by USB barcode scanner |
| Printing | ESC/POS thermal printer (58 or 80 mm) over USB or network |
| HTTPS on LAN | Locally trusted certificate (e.g. mkcert) + setup guide |

**Architecture rule still applies:** the core (face engine interface, members, entitlements, coupons, roles) is plain Python with no dependency on FastAPI, the database driver or the UI, so it can later run in the cloud or be ported to a phone version.

## 4. In scope

| # | Feature | Notes |
|---|---|---|
| 1 | **Staff login with PIN and 3 roles** | admin, checkin, counter. Permissions enforced on the server |
| 2 | **Member registration** | Details form (fields from one config file), consent checkbox with consent text version stored, face capture of 3 frames with basic quality check (face size, blur, brightness, frontal), duplicate face check with admin review, ID-only registration path, delete member |
| 3 | **Excel/CSV import** | Import member details and food choices to save registration time |
| 4 | **Event setup** | One or more events; entitlement slots (e.g. Lunch); options per slot (e.g. Veg, Jain); counters and which options they serve; food choice per member (admin only) |
| 5 | **Check-in (face)** | Identify against members registered for this event; HIGH (confirm), MEDIUM (Yes/No, No leads to search), NO MATCH (retry or search); stored reference photo shown next to live camera; block second slip for same member and slot |
| 6 | **Fallback search** | By member ID, name or mobile, with reference photo for verification; tagged as fallback |
| 7 | **Coupon + printed slip** | Coupon saved as ISSUED before printing; failed print can be retried with the same coupon code; slip layout from `design_dna.md` §9 |
| 8 | **Counter redemption** | Scan QR; check signature, event, slot, status, counter-option match; atomic ISSUED→REDEEMED; full-screen SERVE / ALREADY USED / INVALID / CANCELLED / WRONG COUNTER; if the counter can't reach the server, it pauses and shows "Reconnecting - send to admin desk" |
| 9 | **Admin tools** | Reprint (voids old and issues new in one transaction), void with reason, coupon lookup and admin redemption by lookup if printing fails |
| 10 | **Close event** | Remaining ISSUED coupons become EXPIRED; closure is final; show EXPIRED — DO NOT SERVE |
| 11 | **Simple dashboard** | Registered, checked in, served, counts per option, fallback count |
| 12 | **Audit log** | For registration, edits, deletes, reprints, voids, event close |
| 13 | **Demo data** | Script that creates obviously fake members (no real faces) for demos and tests |

## 5. Out of scope for now (later)

- Phone-only version (on-device face recognition, Bluetooth printing)
- Cloud deployment
- Liveness / anti-spoofing (at the pilot, a volunteer confirms every match in person)
- Product licence keys, multi-customer configuration tooling
- Backup UI (a passphrase-encrypted database + recovery-key archive and a tested restore are required before the pilot)
- Households, attendance-only events, other entitlement types in the UI
- Local-language translations (keep all UI text in translation files, English only)
- Detailed PDF reports (CSV export of counts is enough)

## 6. Rules that still apply

- Member ID is the business identity; face recognition only finds it.
- A human confirms every match before a slip prints.
- One coupon per person per slot; redemption is atomic.
- No face data saved without a consent record; store embeddings plus one small reference photo only; encrypt face data at rest.
- Never log names, mobile numbers or face data.
- Don't hardcode "food" in core logic; use entitlement slots and options.
- No internet required at any point.

## 7. Milestones

| Milestone | Output | Done when |
|---|---|---|
| **M1. Skeleton + face test** | Project setup, core structure, face engine working on the laptop webcam | Enroll 10 people, identify each in ≤ 1 s on the laptop; model licence confirmed; recommended thresholds recorded |
| **M2. Members + events** | Login/roles, registration with face and consent, import, event setup | A member can be registered with face in ≤ 90 s; an event with choices can be set up in ≤ 5 min |
| **M3. Check-in + printing** | Face check-in, fallback search, coupon, printed slip | Full check-in including print in ≤ 15 s; second slip for same member is blocked; printed QR scans reliably |
| **M4. Counter + dashboard** | Redemption, result screens, admin tools, dashboard, close event | Same slip scanned twice (including on two counters at once) gives exactly one SERVE |
| **M5. Pilot readiness** | Phones over local Wi-Fi with HTTPS, dry run with 20 people, quick guides for volunteers | Dry run of 20 people end to end with no errors; setup guide tested on a fresh laptop |

## 8. Demo success criteria

- Complete demo (register → check-in → print → counter → dashboard) in under 10 minutes.
- Works with no internet connection.
- Correct counts on the dashboard after the demo.

See `Decisions_Log.md` for the nine confirmed follow-up requirements, including accuracy, audit, privacy, retries and backup.
