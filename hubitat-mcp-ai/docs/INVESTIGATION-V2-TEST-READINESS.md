# Investigation V2 — Controlled Full-Test Readiness

Status in v0.18.154: **Ready for a broader opt-in READ-ONLY test programme,
not for writes or replacement of production HomeBrain V1**.

## Guardrails and purpose

- The browser at `/v2-test` requires opt-in and the configured operator
  token or authenticated cookie. It must not execute state changes or rules.
- Explicit commands, such as "Turn Livingroom Light 2 on", are blocked before
  a Hubitat inventory read or AI planner call. The error directs the operator
  to the main HomeBrain Ask/Chat interface; it does not forward the command.
  All production write permissions and confirmations remain unchanged.
- V2 reports must separate current source values from timestamped events,
  issued commands from reported states, and verified causality from hypotheses.
- Do not treat source-row absence as proof of no activity, a "connected" MQTT
  client as plug connectivity, or bridge ID 7790 as the initiating automation.

## Recommended ordered test matrix (each test is a new request)

| Test | Example prompt | What constitutes a pass |
| --- | --- | --- |
| Control denial | Turn Livingroom Light 2 on | HTTP 409 `v2_control_not_supported`; zero inventory and MCP calls, no write |
| Polite control denial | Can you turn Livingroom Light 2 off? | Same no-write behaviour |
| Compound command denial | Turn Livingroom Light 2 on and tell me its status | Same no-write behaviour |
| Status only | Is Livingroom Light 2 on? | Verified device #7828, read-time switch status, no fabricated command |
| Switch history | What were Livingroom Light 2's most recent ON and OFF reports? | Timestamped switches, source 7790 treated as reporting bridge, history coverage described |
| Causal question | Why did Livingroom Light 2 change state? | Attempts relevant authorised reads; distinguishes actual controller from reporting source; uncertainty explicit |
| MQTT investigation | Why is Bedroom 3 Mesh offline while MQTT says connected? | Verified device #7103; lastSeen interpreted as a source attribute, not proof of physical state |
| Multiple devices | Compare the reported states of Livingroom Light 1 and Livingroom Light 2 | Both identities independently verified; no accidental single-device narrowing |
| Inventory | Which lights are currently on? | Current reported switch states, complete/incomplete inventory provenance |
| Invalid/ambiguous target | Investigate an unknown device name | Does not guess or switch devices; clear resolution failure |
| Historical ambiguity | What happened to this light last October? | Does not fabricate device identity or historical completeness |
| No-write instruction | Explain the rule controlling Livingroom Light 2. Do not change anything. | Read-only, no Hubitat device or rule mutation |

## What remains experimental

- Full Hubitat inventory retrieval is around 20 seconds in existing live
  measurements; a targeted, independently verifiable lookup remains a goal.
- Complex model-led planning has timed out and may fail to discover all app,
  driver and historical evidence.
- Command-to-initiating-automation attribution is not assured just because
  the reporting source or parent bridge is known.
- Historical pagination and retained Hubitat logs may not cover the incident.
- Safe no-write interpretation is necessary but not proof of production-grade
  natural-language device control.

## Release-to-production criteria (not yet met)

- Repeated live test runs across different device classes with zero V2 writes.
- Control requests never enter investigative MCP loops; read-only questions
  do not get mistaken for commands.
- Every user-facing status and timeline line grounded in typed evidence.
- Model failures do not produce fabricated conclusions or unbounded waits.
- Clear indication of truncation/retention and unverifiable app/driver causes.
- Consistent performance under repeated realistic investigation workloads.

Track results using `answer_mode`, `semantic_diagnostics`,
`reads_executed`, `bootstrap_diagnostics`, `planning_diagnostics`,
`read_failures`, timestamps and source coverage. Preserve full details but
redact access tokens, cookies, passwords and private endpoints before sharing.
