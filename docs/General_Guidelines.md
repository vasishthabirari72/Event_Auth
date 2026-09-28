# General Guidelines

> Current-build override: read `Demo_Scope.md`, `Decisions_Log.md` and
> `Current_Build.md` first. Their explicit laptop/Python/React changes replace the
> historical phone/Flutter requirements below. All unchanged rules still apply.

> Rules every contributor (human or AI coding agent) must follow. If a task conflicts with these rules, stop and flag it instead of working around them.
> Related files: `design_dna.md` (UX), `Technical_Requirements.md` (stack & specs), `Process_Flow.md` (flows), `Implementation_Plan.md` (phases).

---

## 1. The golden rule: protect the core

The product has three layers. Changes flow **top-down only**.

```
Customer configuration   <- per customer, no code
Optional modules         <- reusable features, switched on/off
Core engine              <- identical for every customer, NEVER edited for one customer
```

**Core engine** = face engine, member registry, entitlement engine, security (roles, encryption, audit, backup, licence).

Rules:
1. Core code must never reference a specific customer, event type or food item.
2. Core must not import anything from `modules/` or `config/`. Modules depend on core, never the reverse.
3. Nothing outside `core/face/` may call the face model directly. Use the face engine interface only.
4. Handle every customer request in this order:
   1. Can **configuration** do it? → change config only.
   2. Can it be a **reusable module** other customers could use? → build a module.
   3. Only then: a **customer add-on** that plugs in from outside. Never a core edit.
5. Any core change needs a written reason in the PR and must keep all existing tests passing.

## 2. Product rules (non-negotiable)

- **Member ID is the business identity.** Face recognition *finds* the member ID; it never replaces it.
- **Offline first.** No feature may require internet to work on event day.
- **A human confirms every match.** No automatic slip printing without staff confirmation.
- **One entitlement, one redemption.** Redemption must be atomic. No code path may allow the same coupon to be redeemed twice.
- **Every failure has a fallback.** Face fails → ID/name search. Printer fails → redeem via lookup.
- **Food is just one entitlement type.** Don't hardcode "food" in core logic; use the entitlement model.

## 3. Privacy & biometric data rules

- Store **face templates (embeddings)**, not raw photos, for matching.
- The only image kept is one small, compressed **reference thumbnail** per member, for human verification. It is encrypted at rest and never printed or exported in plain form.
- Record **consent** (who, when, what for, captured by whom) before any face data is saved. No consent → no face data.
- Members under 18 require parent/guardian consent recorded.
- Members can be registered **without** a face (ID-only). This path must always exist.
- Support **delete member** fully: template, thumbnail, personal data. Coupons keep only an anonymised reference for counts.
- Never log faces, embeddings, names or phone numbers to console/crash logs.
- No analytics, telemetry or third-party SDKs that send data off the device.
- Comply with India's DPDP Act 2023. Check applicable local law before selling in any other region.

## 4. Security rules

- Local database encrypted (SQLCipher). Keys stored in Android Keystore via secure storage.
- Coupons are signed (Ed25519). Only check-in devices hold the private signing key; counter devices hold the public key only.
- Staff log in with a role + PIN. Roles: `admin`, `checkin`, `counter`. Enforce permissions in the service layer, not just by hiding buttons.
- Every sensitive action (register, edit, delete, reprint, void, export, settings change) writes an **audit log** entry.
- Backups are encrypted with a customer passphrase.
- Licence key checked at startup; expired licence → read-only mode (export still allowed), never data loss.

## 5. Code standards

- **Language/framework:** Flutter (Dart) for the app. See `Technical_Requirements.md`.
- Follow official Dart style; run `dart format` and `flutter analyze` with zero warnings before every commit.
- **Architecture inside the app:** feature-first folders, with clear layers: `ui` → `state` (Riverpod) → `services` → `repositories` → `data`.
- No business logic in widgets.
- All strings in localisation files (`.arb`). No hardcoded UI text.
- All customer-variable values (fields, food options, colours, labels, enabled modules) come from config.
- Use dependency injection for the face engine, printer and crypto so they can be mocked in tests.
- Prefer small, pure functions for rules (eligibility, redemption checks) so they are easy to test.
- Comments explain **why**, not what.

### Folder structure (target)

```
lib/
  core/
    face/            # face engine interface + implementation (detector, embedder, matcher, liveness)
    members/         # member, household, consent
    entitlements/    # entitlement types, event entitlements, coupons, redemption rules
    security/        # auth/roles, crypto, audit log, licence, backup
    data/            # database, migrations, repositories
  modules/
    food_coupon/     # slip layout, food-specific UI
    attendance/
    households/
    data_import/
  features/          # screens: registration, check_in, counter, dashboard, settings
  config/            # config loader + schema
  l10n/
  shared/            # widgets, theme, utils
test/
  core/ modules/ features/
assets/
  models/            # face model files (versioned)
  config/            # sample customer configs
docs/                # these .md files
```

## 6. Naming conventions

- Files: `snake_case.dart`. Classes: `PascalCase`. Variables/functions: `camelCase`.
- Database tables: plural `snake_case` (`members`, `face_templates`, `coupons`).
- IDs: UUID v4 internally; short human-readable codes for member IDs and coupon numbers (e.g. `HS-0142`, `A7K2-93QX`).
- Config keys: `snake_case`.
- Model files: `face_model_<name>_v<version>.tflite`.

## 7. Testing rules

- **Core engine:** unit tests required for every rule (matching thresholds logic, eligibility, redemption, coupon signing/verification, roles). Target ≥ 80% coverage on `core/`.
- **Redemption:** test concurrent/double redemption explicitly.
- **Face engine:** keep a small consented test image set and a benchmark script that reports match rate, false-match rate and speed on target devices.
- **Printing:** test on each supported printer model before release.
- **Field test:** every release is tried in a real room with real lighting before a customer event.

## 8. Git & workflow

- Branches: `main` (stable), `dev` (integration), `feature/<short-name>`, `fix/<short-name>`.
- Small PRs, one purpose each. PR description: what, why, how tested, screenshots for UI.
- Commit messages: `type(scope): summary` e.g. `feat(counter): add wrong-counter state`.
- Never commit secrets, licence private keys, real member data or real face images.
- Database changes only through versioned migrations.
- Tag releases `vMAJOR.MINOR.PATCH`; keep a `CHANGELOG.md`.

## 9. Configuration rules

- One config file per customer (`customer_config.json`), validated against a schema at load time.
- Config can change: branding, registration fields, food/entitlement options, rules (per person / per household / per slot), enabled modules, languages, counter names, slip text.
- Config can **not** change: security rules, redemption logic, face engine behaviour (except tuned threshold within safe limits).
- Invalid config → app refuses to start that config and shows a clear error to the admin.

## 10. Definition of done (any task)

- [ ] Works fully offline.
- [ ] Follows `design_dna.md` (touch sizes, colours, plain language).
- [ ] No core-layer rule broken.
- [ ] Strings localised; values from config where customer-variable.
- [ ] Tests written and passing; `flutter analyze` clean.
- [ ] Sensitive actions audit-logged.
- [ ] Tested on at least one mid-range Android phone.
- [ ] Docs updated if behaviour changed.

## 11. Instructions for AI coding agents

- Read all five docs in `docs/` before starting any task.
- Work phase by phase from `Implementation_Plan.md`; don't jump ahead.
- If a request would require editing the core for one customer, stop and propose a config or module solution instead.
- Don't add dependencies not listed in `Technical_Requirements.md` without flagging them and checking their licence.
- Never generate or commit fake-but-realistic personal data; use obviously fake names (e.g. "Test Member 01").
- When unsure about a product decision, check "Assumptions to confirm" in `Implementation_Plan.md` and ask rather than guess.
