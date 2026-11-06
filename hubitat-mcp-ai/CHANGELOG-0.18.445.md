# HomeBrainOS 0.18.445 — Adaptive investigation source-progress watchdog

## User mandate

Remove the fixed **180-second total investigation deadline** that cut off
productive evidence gathering even when the AI was obtaining new data.
This is a general read-only orchestration change, not a device-specific fix.

## Implementation

- Ordinary read-only investigation requests no longer pass the old fixed
  `deadline_seconds=180` to `RequestCoordinator.run`.
- The new `investigation_stall_timeout_seconds` (default **180 seconds**)
  limits **time since the last distinct successful read scope**, not elapsed
  request time. A new successful, independently executed read with a different
  gateway/subtool/argument scope renews the window.
- Same-operation retries, failed calls, model thoughts, UI stage updates and
  write-class receipts never reset this inactivity timer. Repeated identical
  source reads cannot prolong a stalled request indefinitely.
- Separate `investigation_emergency_watchdog_seconds` (default **1800
  seconds**) limits runaway requests regardless of progress. This is a
  configurable operational safety ceiling, not a model-quality acceptance
  target. A user's cancellation, browser disconnect, superseding request,
  application shutdown, individual MCP/model timeouts, write confirmation,
  provider quotas and other resource controls remain unchanged.
- Keep the legacy `investigation_deadline_seconds` option (new packaged
  default 0) only for upgrade compatibility; ordinary Ask ignores even a
  previously saved value of 180. A direct coordinator caller can still
  explicitly choose a legacy deadline for testing/compatibility.
- Public progress includes only verified read-scope count and time since
  progress, without device identities/arguments or private model text.
- On stall/emergency cancellation return verified read-only receipts only,
  never unverified model recommendations; return diagnostic 504 when no
  verified sources were collected.

## Limits and evidence quality

One successful *new source scope* can mean an empty page. It measures forward
**investigation activity**, not proof that an original question has been
answered, that source retention is complete, or that an event occurred.
The autonomous evidence/claim verifier still needs further development.
A distinct source scope cannot renew more than the finite in-memory
fingerprint safety budget; the hard watchdog always remains active.

An installed Home Assistant option may preserve legacy values. The new
watchdog defaults apply when the new options are absent. Proxies, browser
disconnects and provider limits may still end a request independently.
The overall model tool-round emergency ceiling is still 18 and was not
removed here. Do not claim general first-answer gains before a source-real
test with the full Technical JSON.

## Verification

Synthetic regression tests exercise extension beyond the former total
cutoff, repeated successful reads, failures/writes, stage chatter,
emergency stop, public progress privacy and normal Ask wiring.
All required repository CI gates must pass before merge. No Hubitat,
Home Assistant, router, private app data, cloud account or device is
modified by this repository release.
