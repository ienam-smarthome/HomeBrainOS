# HomeBrainOS v0.18.160 — Unified incident evidence relationships and read/write boundary tests

## Why

The 27 October v0.18.159 Bedroom 3 Mesh live comparison recovered the original
12 October OFF command from source 3950, the reported switch=off and the later
healthStatus=offline, along with two current stored app settings for controller
3950. However model planning still timed out after 35 seconds on approximately
20,301 input characters and 62 case records; identity lookup took approximately
22 seconds. A successful tool call is not a verified physical cause.

## Architectural improvements

1. **One typed incident link model** (`investigation_v2/transition_links.py`).
   Builds bounded same-target links between an issued command, an optional
   reported switch state and a subsequent adverse health or network observation.
   Used by both controller configuration read priority and the user timeline,
   replacing separately maintained temporal-correlation logic. The link NEVER
   proves causality, physical actuation or Wi-Fi/AP dependency.
2. **Incident-oriented model context**. The full immutable source case is
   retained. Long planning prompts retain all issued commands, switch/availability
   transitions, event-attested settings and context near commands, while repeated
   peripheral observations are represented by first/last samples and explicit
   coalesced counts. The model receives explicit incident links, source coverage
   and their uncertainties. Small-case planning remains lossless.
3. **Source-backed controller configuration reporting**. Typed current stored
   app setting observations are shown separately from the historical incident
   timeline, never claimed to prove 12 October settings or rule execution.
4. **Read/write integration regression**. Synthetic tests exercise the real
   read-only V2 host gate against write gateways and disguised write
   suboperations. Separately, the real confirmed-action coordinator is tested
   against a fake successful Rule Machine write and checked for exactly one
   approved action and a structured verified receipt. No live Hubitat write
   or device control occurs in these tests.

## Remaining limitations

- The configured model provider may still take 35 seconds or time out even
  after context reduction; this release changes the prompt input, not the
  provider transport timeout or runtime AI hardware.
- The initial identity inventory still uses five pages, so its ~22 second
  cost remains for this fixture; a later identity caching/singleflight phase
  should address this separately without trading source freshness.
- A physically self-disconnecting network dependency remains a hypothesis
  until supported by independently observed topology or reachability.
- Integration tests cannot prove a live Hubitat device executed a write.
  The next live write acceptance test requires separately confirmed user
  approval on an intentionally safe test target.

## Live test after deployment

Repeat the same read-only Bedroom 3 Mesh investigation. Compare
`planning_diagnostics.input_chars`, `elapsed_ms`, `stopped_because`,
`bootstrap_diagnostics.controller_config`, the main report's stored settings,
and whether it retains all command/state evidence. Do not modify the device.
