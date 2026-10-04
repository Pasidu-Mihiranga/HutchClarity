# 2026-10-05 - SMS05 - OTP wording that the receiving network delivers

Written by an AI coding agent (Claude Code) for its own change.

## What changed

- httpSMS OTP text: "Clarity sign-in number 123 456. Valid for 5 minutes.
  Never share it." (was "Your Hutch Clarity code is 123456. ...").
- `OtpService.verify` ignores whitespace inside a submitted code.
- The customer sign-in code field keeps digits only (a pasted "123 456" is
  no longer cut to five digits by the length limit).

## Why

Live OTPs to a linked Hutch number were reported "delivered" by httpSMS and
the network but never reached the handset. Diagnostic messages over the same
gateway isolated it: plain text arrived, "Hutch Clarity message with no code"
arrived, "Your Clarity code is 482913" did not. The receiving network drops
OTP-shaped person-to-person SMS ("code is" plus six adjacent digits) while
still returning a delivery report. **ASSUMPTION**: the filter is the carrier's
SMS firewall; a production SMSC route (REQUIRES HUTCH CONFIRMATION) would not
need this wording.

## Validation

- Same-route test of the new wording before the change (Test E).
- `test_httpsms.py` (wording assertion updated with the reason), OTP and auth
  unit tests, OTP delivery parity: passed. ruff, mypy, customer-web tsc: clean.

## Next step

None for the prototype. `CLARITY_SMS_URL` (the SMSC driver) keeps its template.
