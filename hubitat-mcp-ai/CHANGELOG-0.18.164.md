# HomeBrainOS 0.18.164 — device-control receipt reconciliation and write-test lane

## Rationale
The v0.18.163 read-only investigation still timed out during model planning.
Development now prioritises validated control, confirmations and reported state.
Existing routine commands distinguished waitFor failures, but truthy strings such as
"false" could be treated as true; toggles with missing pre-read could be described
as if a changed state were established.

## Changes
- Canonical typed device_command_receipts module distinguishes dispatch failures,
  accepted_unverified, confirmation_missing/invalid/mismatch, not_converged
  and reported_state_converged. The converged field must be literal boolean true.
- If the gateway includes an observed value it must match the requested value,
  with numeric equivalence for brightness and thermostat values.
- DeviceControlService exposes verification_status and aggregate state_verified;
  verified outcome is separate from command acceptance and changed reporting.
- Presenter says command accepted but state unverified rather than falsely
  claiming a toggle changed. Do not automatically retry ambiguous writes.
- Automated simulated Hubitat command suite: on, off, brightness, toggle,
  declined, missing confirmation, false-string, contradictory response,
  not-converged, transport exception and one-write-only safety.
- Existing sensitive-write confirmation, read-only V2 fencing and rule
  reconciliation tests remain in the full CI suite.

## Acceptance after deployment (operator-approved noncritical target)
1. Read exact device state.
2. Turn ON and inspect dispatch, waitFor, and a subsequent fresh state read.
3. Set level to 30% if capability supports SwitchLevel; verify again.
4. Turn OFF and inspect dispatch, waitFor, and a fresh state read.
5. Check an ambiguous or unknown device name causes zero writes.
6. Separately validate a test-only Rule Machine change with same-session approval.

CI executes no live Hubitat writes. A hub-reported attribute is not independent
physical/electrical proof of actuation. Do not control routers, mesh/network
power, refrigerators or security systems for the initial live tests.