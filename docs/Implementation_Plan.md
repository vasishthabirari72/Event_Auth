# Implementation Plan

> Current-build override: read `Demo_Scope.md`, `Decisions_Log.md` and
> `Current_Build.md` first. Their explicit laptop/Python/React changes replace the
> historical phone/Flutter requirements below. All unchanged rules still apply.

> Phase-by-phase build plan for the MVP (Lite tier: Android phone + Bluetooth thermal printer, fully offline).
> Work one phase at a time. A phase is done only when all its acceptance criteria pass.
> Read first: `General_Guidelines.md`, `design_dna.md`, `Technical_Requirements.md`, `Process_Flow.md`.

---

## Decisions this plan is built on

1. Sold as a product to local groups/communities; each customer gets a separate, local, offline setup.
2. One product adapted per customer through config and modules; the face recognition core is never rebuilt or edited per customer.
3. Organizers run registration in person (details, face, food choice, consent).
4. Coupon is a printed slip with a signed QR code.
5. The system must run on just a phone and a printer.
6. Fallback by member ID/name when face recognition fails.

## Assumptions to confirm (don't block Phase 0–2, but confirm before Phase 4)

| # | Assumption | Why it matters |
|---|---|---|
| A1 | Members register once and are reused across events; food choice collected per event | Data model and registration flow |
| A2 | First customers run 1–2 food counters | Whether multi-counter sync (Phase 8) is needed for the pilot |
| A3 | Rule is one coupon per person per meal slot (households optional) | Uniqueness constraint |
| A4 | Android devices only for MVP | Stack choices |
| A5 | English + one local language at launch | Localisation effort |
| A6 | Pilot community identified | Field testing in Phase 10 |

---

## Phase overview

| Phase | Name | Main output | Est. effort* |
|---|---|---|---|
| 0 | Project setup | Repo, CI, app skeleton, docs | 3–4 days |
| 1 | Face POC & calibration | Proof that on-phone face matching works in real conditions | 1.5–2 weeks |
| 2 | Core engine | Face engine interface, data layer, security basics | 2 weeks |
| 3 | Member registration | Registration flow with face, consent, duplicate check | 1.5 weeks |
| 4 | Events & food choices | Event setup, meal slots, selections | 1 week |
| 5 | Check-in + slip printing | Face check-in, signed QR, Bluetooth printing | 1.5–2 weeks |
| 6 | Counter redemption | Scan, validate, redeem once, result screens | 1 week |
| 7 | Fallback, roles & admin tools | Search check-in, PIN roles, reprint/void, audit | 1 week |
| 8 | Multi-counter sync | Host phone + counter phones offline sync | 1.5 weeks |
| 9 | Dashboard, reports, backup, config, licence | Admin completeness | 1.5 weeks |
| 10 | Hardening & pilot | Field test, fixes, pilot at a real event | 2 weeks |

*Estimates assume one experienced Flutter developer; adjust for team size.

---

## Phase 0: Project setup

**Tasks**
- Create Flutter project, folder structure from `General_Guidelines.md` §5.
- Add linting (`flutter_lints` strict), formatting, CI (build + analyze + test on every PR).
- Add Riverpod, Drift + SQLCipher, secure storage, localisation scaffolding.
- Theme from `design_dna.md` (colours, typography, 56 dp targets).
- Put all five docs in `/docs`.

**Acceptance criteria**
- [ ] App builds and runs on a mid-range Android phone.
- [ ] CI green; empty test suite runs.
- [ ] Encrypted empty database opens with key from secure storage.

---

## Phase 1: Face POC & calibration (highest risk, do first)

**Goal:** prove on-device face recognition is fast and accurate enough on target phones in real lighting, before building anything else on top.

**Tasks**
- Select face embedding model; **confirm commercial licence**.
- Build a throwaway POC screen: enroll N people, identify live.
- ML Kit detection + quality gate + alignment + TFLite embedding.
- Active liveness test (blink / head turn).
- Collect a **consented** test set (30–50 volunteers, varied ages, glasses, lighting).
- Benchmark script: match rate, false match rate, time per identify, on 2 device tiers.
- Calibrate HIGH / MEDIUM thresholds; save to model config.

**Acceptance criteria**
- [ ] Identify ≤ 1.5 s on minimum-spec device with 2,000 templates (synthetic templates OK for scale test).
- [ ] No false matches in HIGH band on test set.
- [ ] ≥ 90% of genuine attempts land in HIGH or MEDIUM band in normal indoor lighting.
- [ ] Liveness blocks a phone-screen photo in ≥ 9 of 10 attempts.
- [ ] Written POC report with numbers and chosen thresholds.

**If criteria fail:** try another model/quality settings; if still failing, re-scope (e.g. face only at check-in with mandatory human confirm, or recommend better minimum devices). Decide before Phase 2.

---

## Phase 2: Core engine

**Tasks**
- Face engine interface (`enroll`, `identify`, `checkLiveness`, `findDuplicates`) wrapping Phase 1 code; runs in background isolate.
- Drift schema + migrations for all core tables (`Technical_Requirements.md` §5).
- Repositories for members, templates, consents, events, entitlements, coupons.
- Entitlement engine: eligibility check, coupon creation, atomic redemption, void.
- Crypto service: key generation, Ed25519 sign/verify, QR payload encode/decode.
- Audit log service.
- Config loader + JSON schema validation.

**Acceptance criteria**
- [ ] Core has zero imports from `modules/`, `features/`, `config/` UI.
- [ ] Unit tests ≥ 80% coverage on `core/`.
- [ ] Double-redemption test (parallel calls) always yields exactly one success.
- [ ] Tampered QR payload fails verification.
- [ ] Invalid config is rejected with a clear message.

---

## Phase 3: Member registration

**Tasks**
- Members list with search.
- Register/edit member form driven by config fields.
- Households (module, switchable).
- Consent screen (self / guardian for minors), stored before face capture.
- Face capture UI with live quality hints, auto-capture, retake.
- Duplicate face check with admin review.
- ID-only registration path.
- Delete member (full removal).
- Excel/CSV import of member details (module, optional).

**Acceptance criteria**
- [ ] Register a member with face in ≤ 90 s.
- [ ] No face data saved without a consent record.
- [ ] Duplicate registration of same person is flagged.
- [ ] Deleted member leaves no template/thumbnail in DB.

---

## Phase 4: Events & food choices

**Tasks**
- Create/edit event: date, venue, meal slots, options per slot, counters and which options each serves.
- Add members to event; record food choice per slot (single + bulk).
- Event status: DRAFT → READY → LIVE → CLOSED.
- Pre-event summary: counts per option (shareable to caterer as PDF/CSV).

**Acceptance criteria**
- [ ] Event with 2 slots and 3 options set up in ≤ 5 minutes.
- [ ] Counts per option are correct against test data.
- [ ] After LIVE, only admins can change selections; changes logged.

---

## Phase 5: Check-in + slip printing

**Tasks**
- Check-in screen: camera, face → match card (photo, name, food), HIGH/MEDIUM/NO match states.
- Already-issued detection.
- Confirm & Print: create coupon, sign, render slip (58/80 mm), print over Bluetooth.
- Printer pairing + test print in settings; printer error handling (retry / issue without print).
- Sounds/haptics.

**Acceptance criteria**
- [ ] ≥ 4 check-ins/minute on one desk with a certified printer.
- [ ] Second check-in for same member/slot is blocked.
- [ ] Slip matches `design_dna.md` §9; QR scans reliably from printed paper.
- [ ] Works after phone restart mid-event with no lost coupons.

---

## Phase 6: Counter redemption (single counter)

**Tasks**
- Counter screen: camera scanner + HID scanner input.
- Validation: signature, event, slot, status, counter-option match.
- Full-screen results: SERVE / ALREADY USED / INVALID / WRONG COUNTER / CANCELLED.
- Local used-slip list for standalone counter phone (public key only).

**Acceptance criteria**
- [ ] Scan → result ≤ 1 s.
- [ ] Photocopied slip rejected on second scan with time and counter shown.
- [ ] Counter phone cannot issue coupons (no private key present).

---

## Phase 7: Fallback, roles & admin tools

**Tasks**
- Fallback search (ID / name / mobile) with reference photo verification.
- Staff users + PIN login; roles admin / checkin / counter enforced in services.
- Reprint (voids old), void with reason, coupon lookup/history.
- Walk-in flow (admin adds member to event on the spot).

**Acceptance criteria**
- [ ] Fallback check-in completes in ≤ 30 s.
- [ ] Counter role cannot reach registration or reprint via any path.
- [ ] Voided slip shows CANCELLED at counter.
- [ ] All admin actions appear in audit log.

---

## Phase 8: Multi-counter sync

*(Needed only if A2 shows customers with more than one counter; can move after pilot if not.)*

**Tasks**
- Host mode on admin/check-in phone: local server over hotspot.
- Counter phones pair to host (QR pairing code), send redeem requests.
- Offline fallback on counter (local mode + later sync) with conflict flagging.
- Sync of newly issued coupons to counters (for faster validation).

**Acceptance criteria**
- [ ] Same slip scanned on two counters within 1 s → exactly one SERVE.
- [ ] Counter that loses connection keeps working and syncs later; conflicts shown on dashboard.

---

## Phase 9: Dashboard, reports, backup, config & licence

**Tasks**
- Live dashboard: registered, checked in, served, per option, fallback rate.
- End-of-event report (PDF/CSV, no biometric data).
- Encrypted backup + restore (pendrive, second phone, cloud when online).
- Licence file verification, expiry → read-only mode.
- Customer config packaging: branding, languages, modules on/off.
- Localisation: English + first local language.

**Acceptance criteria**
- [ ] Restore from backup on a fresh phone reproduces all data.
- [ ] Two different customer configs run from the same build with different branding/fields/modules.
- [ ] Expired licence blocks new check-ins but allows export.

---

## Phase 10: Hardening & pilot

**Tasks**
- Load test: 2,000 members, 1,000 check-ins over 2 hours on minimum device.
- Security review (keys, permissions, logs contain no personal data).
- Real-venue dry run with volunteers (lighting, crowd, noise).
- Organizer training material: one-page quick guide per role (check-in, counter, admin).
- Free pilot at one real community event.

**Pilot success metrics**
- Average queue time at check-in and at counter.
- Face match rate / fallback rate.
- Duplicate redemption attempts caught.
- Food count accuracy vs actual consumption.
- Organizer feedback (would they pay? what was confusing?).

**Acceptance criteria**
- [ ] Pilot runs end to end with no data loss and no double servings.
- [ ] Pilot report written with metrics and top 10 improvements.

---

## Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Face accuracy poor on low-end phones / bad lighting | Long queues, trust loss | Phase 1 first; human confirm; fallback; recommend min devices; portable light |
| Face model licence not commercial | Legal block | Verify licence in Phase 1 before any build on it |
| Bluetooth printer incompatibility | Event-day failure | Certify 1–2 models; ship printer in kit |
| Data loss (phone lost/broken) | Customer loses member list | Encrypted backups, end-of-event backup prompt |
| Consent/legal issues with biometrics | Legal/reputational | Consent before capture, ID-only path, delete support, DPDP review |
| Volunteers find app confusing | Adoption failure | `design_dna.md` rules, role-only screens, 2-minute training target |
| Scope creep from custom requests | Core gets forked | Config → module → add-on rule; never edit core per customer |

---

## After MVP (backlog)

- Pro tier: local server kit for large events.
- Other entitlements: kits, drink tokens, zone access.
- Attendance-only events (no food).
- iOS app.
- Customer self-serve config editor.
- Optional cloud sync/dashboard for customers who want it.
