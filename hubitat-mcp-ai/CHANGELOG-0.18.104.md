# HomeBrainOS 0.18.104 — Faster control confirmation, correct pending status

## Live test (24 Oct 2026)

- Single-device TV OFF/ON completed with verified device-state receipts in 1.57s and 1.37s, respectively, without an LLM round.
- A bulk switch-off request correctly staged 11 Internet-room controls and sent **zero writes before confirmation**, but assembling the approval prompt took 28.65s with ~28.4s MCP HTTP and no user-visible evidence receipts.
- After approval, HomeBrain reported 11 successful switch-OFF writes, but took ~39.5s (aggregated 41.2s of MCP queue waiting and 47.6s remote HTTP). The 11 devices were Internet-access control switches, so OFF means blocking access, not necessarily removing physical power.

## Changes

- **Avoid a forced full detailed device inventory at approval staging.** Prefer the pre-existing, TTL-checked, complete local identity snapshot via `peek_device_identities()`. If the structural snapshot has missing command metadata, fall back to the normal TTL-aware detailed device manifest and fail closed if exact targets/capabilities cannot be verified.
- **Keep fresh identity revalidation at approval.** The user must confirm in the same browser session, before the two-minute expiry; confirmation still requests a full fresh detailed manifest and verifies every selected ID, label and supported command before any write. Any changed, missing or ambiguous target cancels the write group. The actual device executor retains per-device remote wait-for-state verification.
- **Report a staged confirmation as `needs_input`,** not `success`. Real failures/refusals remain higher precedence.
- Add scripted-MCP regressions for fast stage, actual forced refresh after confirm, compact structural identity fallback, changed identity refusal and outcome classification. No live physical device writes during tests.

## Limits and follow-up

The repeated **28s staging refresh** should improve when a fresh command-bearing structural identity cache is available, but latency is not yet measured after deployment. Approved 11-device execution still performs 11 remote state changes plus a full fresh identity re-read. The bulk execution's reported 41.2s aggregate queue waiting is not wall-clock delay and may include overlapping commands; this release intentionally does not increase concurrency or relax Hubitat safety just to lower latency. A separate read-only diagnostic of manifest paging and per-device queue timings is the next performance step.

No Hubitat state, rules or user configuration was altered by this code change.
