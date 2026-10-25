# HomeBrainOS 0.18.123 — Investigation V2 typed source adapters and safe planner

## Changes

- Adds reviewed, strictly read-only adapters for ID-matched persisted app
  settings and explicit typed app-execution / transport-ack receipts.
- Preserves read-time snapshots separately from incident-time observations:
  stored settings do not certify effective Groovy runtime behaviour.
- Keeps app log statements, observed executions, acknowledgements, issued
  commands and state reports as separate epistemic stages. Neither an
  acknowledgement nor an OFF command proves a physical OFF.
- Introduces a bounded, non-executing model-proposed investigation read
  validator using live MCP tool manifest/verified discovery, independently
  resolved entity IDs and host read-only effect classification.
- Rejects unadvertised/write operations, fabricated target IDs, malformed
  schema arguments and redundant reads; prevents retrying a capped history
  query solely with a larger history horizon.
- Adds focused unit/replay tests and extends the V2 implementation contracts.

## Availability

**No runtime investigation cutover.** The existing HomeBrain/Hubitat
control and confirmation flow remains unchanged. The planner accepts
AI proposals for host validation but does not call an LLM, perform MCP
reads or publish answers yet. Shadow comparison and cutover require
separate tested development stages.
