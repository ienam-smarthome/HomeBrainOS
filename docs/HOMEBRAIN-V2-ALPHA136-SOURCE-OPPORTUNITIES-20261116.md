# HomeBrainOS V2 alpha.136 — original-source causal read opportunities

**Status:** PR candidate; exact-head CI and installed first-answer acceptance pending.

## Source-real baseline, 16 November 2026

The original uncoached V2 alpha.135 heating WHY first answer ended in a causal
publication-floor partial. The main controlled output was correctly identified
as the main Thermostat (native device history), and a recorded app issued
`command-setHeatingSetpoint` near the last returned heating-state transition.
But **which room actually demanded heating was never established**. The model
incorrectly projected the thermostat's Hubitat grouping as a demand source
and speculated about an evening schedule and event-time temperature.

The source attempts were **3/3 successful**: two broad device inventories
and one 20/20 native thermostat-history page (row limit reached). **Zero**
app-scoped execution log reads and **zero** event-time participating TRV
history reads were made. Causal follow-through and final claim audit each
consumed model rounds without adding evidence. The final fallback prevented
publishing a spurious cause, but did not answer the demanding-room question.
Reported performance: **7 rounds, ~34.7s browser elapsed, 398,189
provider-input tokens**, not a complete or calibrated speed baseline.

### General observed failure

The existing causal controller-decision checkpoint already reminded the
model to consider app execution and event-time input histories, but it
did not identify **which concrete read-only tool arguments were currently
advertised** alongside specific issuer/timestamps from source-bound records.
The model had a large offered catalog and repeatedly reasoned over the
same original receipts rather than selecting discriminating source evidence.

## Implemented general navigation layer (not a forced source planner)

New `rootfs/app/causal_read_opportunity.py` exposes a compact, private
`causal_read_opportunities` index to the **existing** causal source-review
and optional causal follow-through model rounds. The index:

- Only accepts current-request, successful, exact requested-device-bound
  `hub_list_device_events` original responses using the validated
  `native_device_event_receipt` contract. Rejects conflicting native
  identity, event-level mismatches, malformed command names, non-app
  producers and timestamps without offsets. Deduplicates overlapping
  history pages.
- Shows up to four original command issuer/time/device leads, preserving
  multiple timestamps of the **same** command kind. A later
  setHeatingSetpoint command therefore cannot erase earlier event-time
  setpoint evidence from the model's navigation index.
- Indicates whether app-scoped log reads for those issuers were attempted
  and/or succeeded **during this request**, without treating success
  as event-time proof or failure as absence of execution.
- Lists up to six potentially discriminating **actually offered read-only
  tool definitions**, with only their safe exact argument field names,
  types, required flags and short source-advertised string enum values.
  It distinguishes log/execution, event/history, current configuration,
  and read-only gateways whose **leaf contract still requires discovery**.
  It never invents a tool, app ID, leaf, field, filter, log result or rule
  configuration. Raw tool prose, labels, values, logs and free-text
  descriptions are NOT copied into the index.
- Clearly marks **recorded app issuer is not an event-time initiating
  demand, room or controller decision**; offered tool schema is not a
  successful data read or proof of archive availability.

Only the model may decide whether to request another offered read, which
tool to use, its source and arguments, or stop with a bounded unknown.
This adds **no MCP calls, model rounds, automatic app/device selection,
native write or approval change**. It adds a small amount of context to
existing optional causal reviews, so a lower latency or token count is
not yet claimed.

## Fictional tests and required CI

Cross-domain cases cover a thermostat/shared-output controller, lighting,
ventilation, multiple command times, reporter-vs-app issuer, listener-only
metadata, conflicting source ID, failed/native non-device receipts, schema
injection, missing log tool, read-only gateway leaf discovery, model
choosing advertised log reads, and model declining an optional read.
Assertions prohibit automatic dispatch and native writes, preserve original
receipts, and inspect the actual model-round source-review prompt.

Run V2 pilot, full Python, repository validation and UI screenshot CI on
the exact final head before merging; do not treat their passing as proof of
cloud model behavior.

## Source-real acceptance

Update **V2 Preview** to `2.0.0-alpha.136` **only after CI and merge**.
Ask a fresh uncoached read-only historical causal question (heating or a
different domain) and send its FIRST answer with PRIVATE Technical JSON,
including failed or partial answers. Evaluate whether the model chooses
an actual event-time controller execution log or input-history source
when proportionate and advertised. Grade original receipts, not prose:
focal output, timestamp order, reader arguments/limits, recorded issuer,
event-time demand source, user question answered, truthful unknowns,
repeated reads, rounds/tokens/elapsed, and safety. No log read does not prove
the log did not exist; no logged event does not prove none occurred.

Do **not** call this a verified heating-room fix, autonomy improvement or
provider cost reduction until independent source-real evaluations across
different controlled outputs show a reliable gain. Keep V1 and Smart
Thermostat Scheduler untouched. The prior prose regex patch remains
unmerged. Rollback is V2 alpha.135; no data migration required.
