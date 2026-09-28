# Process Flow

> Current-build override: read `Demo_Scope.md`, `Decisions_Log.md` and
> `Current_Build.md` first. Their explicit laptop/Python/React changes replace the
> historical phone/Flutter requirements below. All unchanged rules still apply.

> How the product works end to end: from a new customer's setup to event-day check-in, counter redemption and after-event wrap-up.
> Diagrams use Mermaid (renders on GitHub, VS Code with Mermaid preview, Notion, etc.).

---

## 0. Big picture

```mermaid
flowchart LR
  A[Customer onboarding] --> B[Member registration drive]
  B --> C[Create event + food choices]
  C --> D[Event day: check-in + slip]
  D --> E[Food counter: redeem]
  E --> F[After event: report + backup]
  F --> C
```

Members are registered **once** and reused across events. Food choice is collected **per event**.
*(Assumption: confirm with first customer. See `Implementation_Plan.md`.)*

---

## 1. Customer onboarding (done by us)

```mermaid
flowchart TD
  A[Discovery call with committee] --> B[Fill onboarding questionnaire]
  B --> C[Create customer_config.json]
  C --> D[Generate licence key + signing keys]
  D --> E[Install app on customer phones]
  E --> F[Pair Bluetooth printer + test print]
  F --> G[Create admin account + PIN]
  G --> H[Train organizers: 20 min demo]
```

**Onboarding questionnaire covers:** group size, number of events per year, meals per event, food options, household rules, number of check-in desks and food counters, devices available, languages, whether members have existing ID cards or an Excel list.

---

## 2. Member registration drive

Organizers run a registration desk. Members come in person.

```mermaid
flowchart TD
  A[Admin logs in] --> B[Search member by name/mobile]
  B -->|Exists| C[Open member]
  B -->|New| D[Enter details: fields from config]
  D --> E[Link to household - optional]
  C --> F{Member consents to face capture?}
  E --> F
  F -->|No| G[Save as ID-only member]
  F -->|Yes| H{Under 18?}
  H -->|Yes| I[Record guardian consent]
  H -->|No| J[Record member consent]
  I --> K[Face capture with live quality guide]
  J --> K
  K --> L{Quality OK?}
  L -->|No| K
  L -->|Yes| M[Liveness check]
  M -->|Fail| K
  M -->|Pass| N[Duplicate face check vs all members]
  N -->|Possible duplicate| O[Show existing member for admin review]
  O -->|Same person| P[Cancel - use existing record]
  O -->|Different person| Q[Save with admin override - logged]
  N -->|No duplicate| R[Save template + thumbnail]
  Q --> R
  R --> S[Audit log entry]
  G --> S
```

**Target:** under 90 seconds per member.

---

## 3. Event setup

```mermaid
flowchart TD
  A[Admin: Create event] --> B[Name, date, venue]
  B --> C[Meal slots e.g. Lunch, Dinner]
  C --> D[Entitlement options per slot e.g. Veg, Jain]
  D --> E[Rules: per person / per household]
  E --> F[Counters: names + which options each serves]
  F --> G[Add members to event + record food choice]
  G --> H[Review counts per option]
  H --> I[Share counts with caterer]
  I --> J[Mark event READY]
```

Food choice can be added in bulk (import) or one by one. Changes are allowed until the event is marked **LIVE**; after that only admins can change, and every change is logged.

---

## 4. Event day: check-in (face path)

```mermaid
flowchart TD
  A[Check-in volunteer opens Check-in screen] --> B[Member faces camera]
  B --> C[Face detected + quality check]
  C -->|Poor| B
  C --> D[Liveness check]
  D -->|Fail| B
  D --> E[Match against members registered for THIS event]
  E --> F{Match confidence}
  F -->|High| G[Show match card: photo, name, food]
  F -->|Medium| H[Amber card: Is this NAME? Yes/No]
  F -->|None| X[Not recognised -> Fallback flow]
  H -->|No| X
  H -->|Yes| G
  G --> I{Already has slip for this slot?}
  I -->|Yes| J[Red card: already issued at TIME - admin reprint only]
  I -->|No| K[Volunteer taps Confirm & Print]
  K --> L[Create coupon + sign QR]
  L --> M[Print slip]
  M -->|Printer error| N[Retry / Mark as issued without slip]
  M -->|OK| O[Coupon status = ISSUED, audit log]
```

**Matching scope:** only members registered for this event (smaller list = faster and more accurate). If not found there, the app can offer "Search all members" for walk-ins, which requires admin approval to add them to the event.

---

## 5. Fallback: face not recognised / member without face

```mermaid
flowchart TD
  A[Tap Search by ID/name/mobile] --> B[Type query]
  B --> C[Results list with reference photo]
  C --> D[Volunteer compares photo with person]
  D -->|Match| E[Continue from step I of check-in flow]
  D -->|No photo on file| F[Ask for member card / known to committee]
  F -->|Verified| E
  F -->|Not verified| G[Send to admin desk]
```

Every fallback check-in is tagged `method = fallback` for reporting.

---

## 6. Food counter: redemption

```mermaid
flowchart TD
  A[Counter volunteer opens Counter screen] --> B[Scan slip QR]
  B --> C{Signature valid?}
  C -->|No| R1[RED: Invalid slip]
  C -->|Yes| D{Correct event + slot?}
  D -->|No| R2[RED: Not valid for this event/meal]
  D -->|Yes| E{Coupon status}
  E -->|VOID| R3[RED: Slip cancelled]
  E -->|REDEEMED| R4[RED: Already used at TIME, COUNTER + member name]
  E -->|ISSUED| F{This counter serves this option?}
  F -->|No| R5[AMBER: Go to COUNTER NAME]
  F -->|Yes| G[Atomic update: ISSUED -> REDEEMED]
  G --> H[GREEN full screen: SERVE + food choice + name]
  H --> I[Auto return to scanner]
```

**Atomic update** means the check-and-mark happens in one database transaction. If two counters scan the same slip at the same moment, only one succeeds.

---

## 7. Coupon lifecycle (state machine)

```mermaid
stateDiagram-v2
  [*] --> ISSUED: Check-in confirmed + slip printed
  ISSUED --> REDEEMED: Valid scan at counter
  ISSUED --> VOID: Admin reprint / cancel
  VOID --> [*]
  REDEEMED --> [*]
```

- Reprint = old coupon → `VOID`, new coupon → `ISSUED` (new coupon number).
- `REDEEMED` is final. Only an admin can add a note; it can never go back to `ISSUED`.
- Every transition is audit-logged with device, staff user and time.

---

## 8. Multi-counter sync (Lite setup, offline)

Only needed when there is more than one counter.

```mermaid
sequenceDiagram
  participant C1 as Counter phone 1
  participant H as Host phone (hotspot)
  participant C2 as Counter phone 2
  C1->>H: Redeem request (coupon id)
  H->>H: Atomic check & mark REDEEMED
  H-->>C1: Result (valid / already used)
  C2->>H: Redeem same coupon id
  H-->>C2: Already used at TIME, Counter 1
```

- One phone is the **host** (usually the admin/check-in phone). It holds the master coupon table.
- Counter phones send redeem requests over local Wi-Fi hotspot; the host decides.
- **If a counter loses connection:** it switches to *local mode* (verifies signature, keeps its own used list), shows an amber "Offline mode" badge, and syncs its redemptions when reconnected. Conflicts found on sync are flagged in the dashboard.
- Single-counter setups skip sync entirely: the counter verifies signatures and keeps its own used list.

---

## 9. Admin exceptions

| Situation | Action | Who |
|---|---|---|
| Member lost slip | Look up member → Reprint (voids old) | Admin |
| Wrong food chosen | Void coupon → change choice → reissue | Admin |
| Walk-in not registered for event | Add to event + choose food → check-in | Admin |
| Suspected misuse (already-used scans) | Check audit log / coupon history | Admin |
| Printer out of paper / broken | Switch printer or use "redeem by lookup" at counter | Admin |
| Member wants data deleted | Delete member (template, photo, details) | Admin |

---

## 10. After the event

```mermaid
flowchart TD
  A[Admin marks event CLOSED] --> B[Unredeemed coupons auto-expire]
  B --> C[Dashboard summary: registered, checked-in, served, per food option, fallback rate]
  C --> D[Export report PDF/CSV - no face data]
  D --> E[Encrypted backup to pendrive / second phone / cloud when online]
  E --> F[Sync redemptions from counter phones]
```

---

## 11. Role permissions summary

| Action | Admin | Check-in | Counter |
|---|:-:|:-:|:-:|
| Register / edit / delete members | ✅ | ❌ | ❌ |
| Create / edit events | ✅ | ❌ | ❌ |
| Face check-in + print slip | ✅ | ✅ | ❌ |
| Fallback search check-in | ✅ | ✅ | ❌ |
| Redeem slips | ✅ | ❌ | ✅ |
| Reprint / void | ✅ | ❌ | ❌ |
| Dashboard | ✅ | counts only | ❌ |
| Backup / settings / staff PINs | ✅ | ❌ | ❌ |
