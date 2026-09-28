# M3 — check-in and signed QR PDF

Current output is a PDF, as requested. No thermal driver or printer is required.
Face matching remains experimental; do not use this as an accuracy acceptance report.

## Setup
1. Run `uv sync --locked` and `npm --prefix frontend ci` when setting up a new machine.
2. Load `.env`, then run `.venv/bin/alembic upgrade head` (migration 0003).
3. Set `EVENT_AUTH_SIGNING_KEY_FILE` to a private path outside the project, for example
   `$HOME/.local/share/event-auth/coupon-signing.key`.
4. Provision once with `.venv/bin/python -m event_auth.adapters.signing "$EVENT_AUTH_SIGNING_KEY_FILE"`.
   This refuses overwrites. Existing installations must retain their original key.
5. Build the frontend and restart the local server using the README commands.

The storage encryption key and the signing key are distinct. Back up both securely.
No private key, raw frame or embedding is included in PDF/browser responses.

## Try the flow
1. Register a member (face optional), create an event, record choices and mark it READY.
2. As admin open **Check-in**, choose the event and **Start event check-in**.
3. Choose a slot. A check-in staff account can now use the same event.
4. For the face path, confirm the participant's agreement and existing consent, open
   camera and **Scan face**. Matching only searches members registered for this event.
5. Compare the actual person with the reference photo and name. HIGH requires confirmation;
   MEDIUM shows Yes/No (Yes confirms and issues); No goes to search. No match offers retry/search.
6. For fallback, search ID/name/mobile. Verify the photo or use member card/committee verification.
7. **Confirm identity & create QR PDF**, then **Download QR PDF**. The coupon is already
   saved before PDF generation. A failed download can be retried with the same coupon.
8. Try the same member and slot again: the existing coupon is shown and a new issue is blocked.
   You can retrieve the same PDF; this is not an admin replacement/reprint operation.

The PDF includes organization, event, slot, choice, name, member ID, coupon code, issued
UTC time and signed QR. It excludes mobile, address and face photos. One coupon per slot.
Downloaded PDFs contain member names; handle them like the intended printed slips.

## Output extension
`core/documents.py` defines a platform-independent `CouponDocument` and `DocumentOutput` port.
`adapters/pdf.py` is the current renderer, injected by the composition root. A future printer
integration consumes the same immutable coupon data after issuance; it must never create
another entitlement. Physical dispatch/acknowledgement belongs in a separate transport adapter
for the selected USB, network or other printer. No unsupported printer is claimed to work.

PDF render counts are server attempts completed, not confirmed physical prints. M4 adds
redemption, admin void/replacement, closure and counts. Do not treat M3 as an event-ready system.
