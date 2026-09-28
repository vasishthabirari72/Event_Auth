# Design DNA

> Current-build override: read `Demo_Scope.md`, `Decisions_Log.md` and
> `Current_Build.md` first. Their explicit laptop/Python/React changes replace the
> historical phone/Flutter requirements below. All unchanged rules still apply.

> Working name: **Event Auth** (final product name TBD)
> Purpose of this file: define *who we design for, how the product should feel, and the visual/interaction rules every screen must follow.* Read this before designing or building any screen.

---

## 1. Product in one line

An offline, phone-first system that lets community organizers register members with their face, identify them at events, and issue one-time printed food coupons that can't be reused.

## 2. Who we design for

| User | Who they are | What they need |
|---|---|---|
| **Admin organizer** | Committee secretary / treasurer / event head. Moderately tech-comfortable. | Set up the event, register members, see live counts, fix problems (reprint, void). |
| **Check-in volunteer** | Committee member or helper. May be older, may not be tech-savvy. Standing, in a crowd, often outdoors. | Point phone at face, confirm, print slip. Nothing else. |
| **Counter volunteer** | Often the caterer's staff or a young volunteer. Busy, both hands occupied. | Scan slip, see green/red instantly, serve the right food. |
| **Member** | Community member of any age, including elderly and children. Never touches the app. | Get through the line fast and get the right food. |

**Design target:** a 55-year-old volunteer who has never seen the app should be able to do check-in or counter duty after a 2-minute demo.

## 3. Core principles

1. **Offline is normal, not an error.** The app never shows "no internet" warnings. Nothing depends on a network.
2. **One screen, one job.** Check-in screen only checks in. Counter screen only redeems. No menus to get lost in during an event.
3. **Speed over completeness on event day.** Every event-day action must finish in a few seconds. Admin tasks (reports, edits) can be slower.
4. **The organizer is always in control.** The system suggests a match; a human confirms. Face recognition never silently decides.
5. **Every failure has a next step.** No dead ends. Face not matched → "Search by ID or name". Printer offline → "Retry / Redeem without slip".
6. **Trust through clarity.** Always show *who* was matched (name + stored photo) and *what* they get (food choice), so staff can catch mistakes.
7. **Privacy by default.** Store face templates, not photo galleries. Show consent clearly. Minimum personal data.
8. **Same core, different faces.** Branding, fields and wording change per customer through configuration; the interaction patterns never change.

## 4. Environment constraints (design for these)

- Bright sunlight or dim hall lighting.
- Noise, crowds, people pushing the queue.
- One-handed use; phone often on a stand at check-in.
- Mid-range Android phones (not flagships).
- Volunteers wearing reading glasses or none.
- Mixed languages in the same community.

## 5. Visual language

### Colour (semantic first)

| Role | Use | Suggested value |
|---|---|---|
| Success | Valid slip, match confirmed, printed | Green `#1B873F` |
| Danger | Already used, invalid, void | Red `#C62828` |
| Warning | Low-confidence match, wrong counter, printer issue | Amber `#B26A00` |
| Primary | Main action buttons | Customer brand colour (from config), default deep blue `#1E4FA3` |
| Surface | Background | White / near-white `#FAFAFA` |
| Text | Body text | Near-black `#1F2937` |

Rules:
- Result screens (counter) fill the **whole screen** with the state colour. Readable from 2 metres away.
- Never rely on colour alone: every state also has an icon and a word ("SERVE", "ALREADY USED", "WRONG COUNTER").
- Minimum contrast ratio 4.5:1 for all text.

### Typography

- One sans-serif family with good Indian-script support (e.g. Noto Sans + Noto Sans Devanagari).
- Body minimum 16 sp; labels 14 sp minimum; result words on counter screen 48 sp+.
- Food choice text is always the largest thing on any screen it appears on.

### Layout & touch

- Minimum touch target 56 × 56 dp (larger than standard, for gloves/rush/older users).
- Primary action always at the bottom, full width, reachable by thumb.
- Maximum 2 actions visible on event-day screens.
- No hidden gestures (no swipe-to-delete, no long-press-only actions).

### Iconography

- Simple outline icons, always paired with a text label on event-day screens.

### Sound & haptics

- Distinct short sound + vibration for success and for failure on the counter screen (volunteers may not be looking at the screen).
- Sounds can be turned off in settings.

## 6. Language & tone

- Plain, short, action-first words: "Scan face", "Print slip", "Serve: JAIN".
- No technical terms on staff screens (never "embedding", "threshold", "sync conflict").
- UI strings live in translation files from day one; English first, local languages added through config.
- Friendly, never blaming: "Couldn't recognise. Try again or search by name." not "Recognition failed."

## 7. Screen inventory (MVP)

| # | Screen | Used by | Key elements |
|---|---|---|---|
| 1 | Setup / licence activation | Admin | Licence key, organisation name, admin PIN |
| 2 | Home (role-based) | All | Only shows tiles the logged-in role can use |
| 3 | Members list | Admin | Search, add, edit, household, face status badge |
| 4 | Register member | Admin | Details form (fields from config), consent, face capture with live quality guide |
| 5 | Events list / create event | Admin | Name, date, meal slots, food options, counters |
| 6 | Event registration (food choice) | Admin | Member search → pick food per slot |
| 7 | Check-in | Check-in volunteer | Camera, match card (name + stored photo + food), Confirm & Print |
| 8 | Fallback search | Check-in volunteer | Search by ID / name / mobile, photo to verify |
| 9 | Counter redeem | Counter volunteer | Scanner view → full-screen result |
| 10 | Dashboard | Admin | Registered / checked-in / served / food counts per option |
| 11 | Slip management | Admin | Reprint, void, lookup coupon |
| 12 | Settings & backup | Admin | Printer pairing, export backup, staff PINs, language |

## 8. Key interaction patterns

### Face capture guide (registration)
- Oval overlay; live hints: "Move closer", "More light", "Look straight", "Remove mask".
- Auto-capture when quality is good (3 frames), with manual capture as backup.
- Show captured result and let admin retake before saving.

### Match card (check-in)
- Stored photo thumbnail (from registration) side by side with live camera.
- Name, member ID, food choice for this event.
- High confidence → green border, big "Confirm & Print".
- Medium confidence → amber border, "Is this [Name]?" with Yes / No, search.
- No match → "Not recognised" + "Try again" + "Search by name/ID".
- Already checked in → red card: "Slip already issued at 1:14 PM" + admin reprint option.

### Counter result
- Full-screen colour, icon, one big word, food choice, member name, then auto-return to scanner after ~2 seconds (configurable).

## 9. Printed slip design (58 mm / 80 mm thermal)

```
+--------------------------------+
|   [ORG NAME]                   |
|   Diwali Get-together 2026     |
|   Lunch                        |
|--------------------------------|
|   ##  JAIN  ##                 |   <- largest text, bold, inverted if printer supports
|--------------------------------|
|   Priya Sharma                 |
|   Member ID: HS-0142           |
|                                |
|        [  QR CODE  ]           |
|                                |
|   Coupon #A7K2-93QX            |
|   Issued 12:41 PM · Desk 1     |
|   Valid once · This event only |
+--------------------------------+
```

Rules:
- Food choice is readable from arm's length.
- QR is the only authority; printed text is for humans.
- No sensitive data on the slip (no mobile number, no address, no face image).

## 10. What we deliberately avoid

- Dashboards on event-day volunteer screens.
- Anything that requires typing during check-in (except fallback search).
- Pop-up confirmations stacked on top of each other.
- Tiny text, grey-on-grey, thin fonts.
- "AI magic" language in the UI. It's a tool, not a gimmick.
