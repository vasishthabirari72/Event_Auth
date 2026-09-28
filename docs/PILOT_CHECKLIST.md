# Pilot acceptance record

Status: NOT READY FOR PILOT. Owner deferred camera testing while M5 tooling proceeds.
Check items only with evidence; automated tests do not replace physical trials.

## Before scheduling
- [ ] Owner reviews consent wording and guardian procedure.
- [ ] Formal face evaluation: ten consenting participants, separate enrollment/validation,
  unknown people, zero HIGH false matches and >=90% genuine HIGH/MEDIUM in normal light.
- [ ] Full identification <=1 second at 300 members on the pilot laptop; record hardware,
  model/config versions and attempts. Record 6,000-template benchmark separately.
- [ ] Check-in including current PDF output <=15 seconds; fallback <=30 seconds.
- [ ] Real QR camera/USB-scanner reliability and scan-to-result <=1 second.
- [ ] Two physical counters scan the same coupon: exactly one SERVE.
- [ ] Trusted HTTPS and camera permissions on every intended phone/browser.
- [ ] Fresh-laptop setup completed using only the written guide.
- [ ] Owner performs an encrypted backup/restore drill using the intended backup drive.
  Automated fake-data restore is already covered; actual operating procedure is separate.

## Venue preparation
- [ ] Laptop power/charger, phone power banks, clean lenses and usable front lighting.
- [ ] Private router/hotspot, reserved laptop IP, client connectivity and subnet firewall rule.
- [ ] Dependencies, Docker images, model weights and UI already provisioned locally.
- [ ] Disconnect internet; keep local Wi-Fi; verify app, PDF and counter operation.
- [ ] Separate admin/check-in/counter accounts; volunteers trained with STAFF_GUIDES.md.
- [ ] Correct event/slot/choices/counter assignments; new event available for test closure.
- [ ] Backup drive/passphrase procedure and one serving authority agreed.
- [ ] Ordinary PDF output/QR presentation tested. Thermal driver/physical thermal acceptance
  remains deferred until the owner resumes printer integration.

## Twenty-person dry run (pending)
Record date, devices, network, participants/consent, timings and failures in a new report.
Use genuine and ID-only paths, imported member enrollment, wrong counter, duplicate,
replacement/void, lookup fallback and final closure. Disconnect a counter during a request:
no local serving, retry recovers the original outcome. Restart the laptop service and
verify issued/redeemed state survives. Reconcile final counts with observed servings.
Confirm no duplicate servings or data loss. Time the complete committee demo (<10 minutes).

## Evidence already available
- M4 automated single-use/concurrency/retry/closure/privacy checks: M4_STATUS.md.
- M5 encrypted fake-data restore and local certificate-verified HTTPS: M5_STATUS.md.
- Two-person recognition success: owner-reported, not formal accuracy acceptance.

Missing physical checks remain pending; advancing development does not waive them.
