# HomeBrainOS v0.18.203 — Bounded cross-occurrence correlation and focused read scope

## Live input

The v0.18.202 Google Nest Hub investigation (29 October 2026) returned an isolated generic excessive-load warning at 06:01:28.979 and a device-produced volume=50 event with the exact same source-reported timestamp. Earlier investigations returned volume=10 near the 01:03:20 warning and buffering/idle changes near the 28 October 19:55:19 warnings. This is a potentially useful *association* across occurrences, **not** proof the volume callback caused CPU load. The latest single-run log history only returned one matching warning: independently collecting past warnings is still required to conclude that the full pattern was recovered within V2.

The live run spent 24.993 seconds on seven reads, including an unscoped hub event query and a duplicate WARN sample; the source code of the driver was unavailable and the caller was not established.

## Changes

- Introduce a general, independent, typed warning/state association analyzer. For each independently source-reported discrete warning timestamp for the verified target, compare device-produced state timestamps within a bounded 0–10-second tolerance, default ±2 seconds. Preserve warning read IDs, event read IDs, exact source-reported millisecond gaps, separate incident occurrences, counts, source caps and unknown clock alignment. Deduplicate warning records re-seen through different log reads. **No link from temporal coincidence to callback, app, command, CPU consumption or root cause.**
- Surface the results in the existing host-authoritative generic-warning incident packet and final report. Source data are bounded and allow-listed: no raw mediaSource contents, arbitrary event values or private configuration reach the association.
- Once the host has verified exactly one device focus, a device-event read missing both target scope and an explicit hub-wide mode is rejected even if the targeted WARN has not yet been fetched. This prevents silent consumption of unscoped hub-mode/location events as target history. Model may explicitly choose an intentional hub-events mode or a target-specific deviceId; all existing read-only, live-schema and ID guards remain in force.
- Cue the model to ask for scoped device history and avoid duplicate warning records. Exact and subset duplicate detection still occurs after a real read: a different historical time scope is not suppressed merely because it *might* return the same events; future independent evidence must remain recoverable.
- Add regression tests for multiple warning instants, matching and nonmatching state events, duplicate reads, unrelated devices, app-issued commands, privacy, unscoped event calls and incomplete timestamp observations.

## Limits

This is **correlation evidence only**, not a full runtime tracing system or causal root-cause detector. Current V2 cannot supply unavailable driver code or runtime CPU profiles. Source timestamps may have mismatched time zones, event histories are bounded, and legacy grouped-only log evidence cannot be converted into precise occurrence timestamps. Production Main Ask and Hubitat devices/rules are unchanged; Native V2 remains READ-only.

## Next acceptance

After CI and merge, run Native V2 investigation on the Nest Hub. Verify warning occurrence count, exact reported delta for nearby volume state, no conflation with command issuers, explicit driver-source blocker, and rejection of unscoped target history. Independent live testing is required before claiming improved performance.
