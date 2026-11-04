# 0.18.390 — Q1 read-only recovery after rejected model writes

## Problem observed (installed v0.18.389, 2026-11-04)

A read-only, six-objective Hubitat preflight returned a partial answer after 25.925 seconds
(23.042 seconds provider, 2.430 seconds MCP, 5 Gemma rounds, 2 executed
MCP reads, 1 discovery). The technical receipt recorded
`read_only_model_write_blocked=2`; no unauthorized change was made.
The model reported a hub clock, but did not source-establish the requested
hub-local backup, installed MCP version, virtual-device tool availability,
isolated test-switch inventory or native dated-rule inventory. The API
transport reported `success=true`, which is not the same as question
resolution or successful Internet blocking. The first-attempt prompt and
deployed SHA were not independently authenticated.

## General improvement

When a model suggests a write in a request with **no independent user write
authorization**, HomeBrain already rejects the *entire proposed batch*,
including any companion read. It now switches the remaining model turns
to a bounded, **actually installed read-only capability view**, lists those
read tools in the existing conversation and explicitly states that no
companion read ran. The view remains read-only after further discovery.
This keeps natural, model-authored explanation, avoids repeating the same
write-capable tool schema and can let the model complete outstanding reads.

A missing read tool stays missing. No rejected call is replayed, no source
result or tool is invented, no confirmation is queued, and the existing
write-authority, read-only effect-classification, MCP permissions and
confirmation gates are unchanged. Authorized write requests continue down
their preexisting path.

## Acceptance and limitations

- Fake-tool regressions cover an atomic mixed write/read rejection followed
  by verified read-tool recovery; a registry lacking the requested reader;
  no Hubitat write; and preservation of user confirmation for authorized
  virtual-device creation by the existing v0.18.389 tests.
- The latest observed **live** pre-change receipt is one partial six-check
  preflight on v0.18.389, not an exact SHA/prompt-attested frozen
  before/after benchmark. There is no live v0.18.390 outcome yet.
- Expected direction: fewer repeated blocked write proposals and better
  first-answer source coverage. Actual improvement, first-attempt quality,
  median/p95 and Claude comparison remain **NOT MEASURED**.
- Production Internet-blocking and both offline native dated/delay BAT
  writers remain disabled. No Hubitat, Home Assistant or router changes.
- Rollback: revert this focused read-only recovery change if a read workflow
  loses needed verified capabilities or any write boundary regresses.
