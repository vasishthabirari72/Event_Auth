# M4 — counter redemption and administration

M4 is available for local development. Recognition accuracy and real counter-device
performance are still under evaluation. Current coupons are PDFs; no thermal driver
is required. Keep the existing signing and encryption keys when upgrading.

## Counter test
1. In Check-in, issue and download a coupon for a member registered in a LIVE event.
2. Open Counter as an admin or counter staff member. Select the event, slot and counter.
3. Start the camera and hold the coupon QR from another screen or paper in view.
   A USB keyboard scanner may instead enter the full QR text into the input and press Enter.
   A coupon's short printed code is for admin lookup, not the signed QR input.
4. Serve only on the fresh green SERVE result. Scanning the same coupon again gives
   ALREADY USED. WRONG COUNTER names the eligible counter; other red states do not serve.
5. Remove the QR from view before presenting another coupon. Sound can be disabled.

If the connection fails, stop serving and use Retry when it returns. Retry preserves
its request ID and displays RECOVERED with the earlier outcome, never a new instruction
to serve. Send uncertain cases to the admin desk. Reloading loses the pending browser
request, so the admin must check server history before deciding what happened.

The camera requires localhost now. Do not expose the development HTTP server to phones;
trusted LAN HTTPS and phone validation are M5 work. To try a QR with one laptop, use
an ordinary printer or display the downloaded PDF on another device; that device does
not need access to the app. Physical scanner/camera speed remains to be measured.

## Administrator
Dashboard shows registered members, unique checked-in people, issued entitlements,
served entitlements, fallback entitlements and per-slot/option counts. Use Refresh
for current counts; the CSV contains aggregate codes/counts only. Multiple slots can
make issued greater than checked in. Replacements do not increase entitlement counts;
deleting a member retains anonymous historical counts but reduces current registrations.

Search coupon history by coupon code, member code or name. Select the relevant counter
before lookup redemption. Confirm the action; lookup uses all normal redemption checks.
Replace an unused coupon with a reason to cancel the old QR and download its replacement.
A download retry retains the same QR; replacement creates a new one. Used coupons cannot
be replaced. Void cancels an unused coupon without immediately creating a replacement.

Closing an event is final. It expires every outstanding coupon and blocks new issuance,
redemption and replacement. Use a disposable demo event when testing closure.

## Configuration and upgrade
Customer configuration accepts `counter_result_seconds` (1–10, default 2.5) and
`counter_sounds` (default true). Recovery notices remain visible for at least six seconds.
These settings affect presentation only, never redemption rules. Restart after config edits.

Use the existing README upgrade commands: stop the app, load `.env`, run
`.venv/bin/alembic upgrade head`, build the frontend, then restart. Migration 0004
preserves existing coupons and keys. Do not recreate the signing key. No additional
runtime dependency was introduced for M4.

See M4_STATUS.md for automated evidence and outstanding physical acceptance.
