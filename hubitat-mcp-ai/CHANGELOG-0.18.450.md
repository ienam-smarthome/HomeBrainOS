# HomeBrainOS v0.18.450 — Causal claims checked against exact source roles

## Source-real failure

A v0.18.449 installed read-only investigation recovered the latest recorded
light ON/OFF interval and an earlier directly attested ON command but still
mixed verified evidence with unsupported conclusions. The final answer
interpreted a Hue/Matter bridge-reported physical state event as evidence of
external control and a bounded command page with no matching OFF row as proof
that Hubitat had issued no instruction. The single independently confirmed
focal sensor observation was `motion=inactive`, not generic activity. A
controller-boundary correction inserted an unrelated historical interval
into the focal question. The output also described downstream subscribers
as necessarily not the initiators, despite possible independent command
paths.

The user supplied complete Technical JSON. The most recent OFF initiating
controller is not established. No native `command-off` row was attested at
that focal instant, but history completeness was not independently verified.
A targeted app-configuration read failed and historical app logs could not
establish the decision. One source-real evaluation failed; this does not
establish any broader model-quality percentage.

## General implementation

- Keep a correct source-reported bridge-state statement while removing the
  unsupported phrase claiming the action "occurred outside Hubitat's control".
  Expand command denial validation to statements about a command "being issued
  by Hubitat". Qualify absence to the source pages actually queried.
- A downstream subscriber does not establish or refute an independent
  initiating route. Replace categorical "listeners rather than triggers"
  exclusion with role-qualified wording.
- When a typed unique requested OFF boundary exists, only that focal interval
  can support the controller boundary repair; do not import an unrelated
  earlier interval because of a generic "controller" keyword.
- New general source-bound sensor-value guard carries a positive
  `attribute=value` from a matching focal correlation and independently
  successful native absolute-window event, only if unambiguous and referred
  to by the sentence. Never promote journal reception timestamps into
  original event times, or empty sensor queries into negative observations.
- Run exact sensor-value check in both synthesis validation and read-only API
  publication; surface `focal_sensor_value_corrected` only when applied.
- Synthetic tests cover bridge inference, bounded command absence, listener
  role, exact negative sensor value, unrelated sensor and older transition,
  old controller interval, API full path and write/confirmation exemptions.

## Quality and safety

All four mandatory CI workflows passed on exact tested PR head `405f4fce996a86dacc37f41b8a70491224a8a055`; [PR #1505](https://github.com/ienam-smarthome/HomeBrainOS/pull/1505) squash-merged as `6264be5f646eadd0475d1d2bb58c3d0df0bce41b`. The first candidate run exposed one missing runtime-module-map entry, corrected before the final green run.
A successful release proves the source-checking code paths, **not** first-pass
model reasoning improvement. Preserve observed positive ON command, unknown
OFF initiator, historical completeness limits, confirmed sensor value and
reported-state timeline. No new MCP reads, device/automation changes, paid
routing change, provider selection change or watchdog relaxation.

After installing the merged add-on, repeat a fresh read-only causal question
with full Technical JSON. Attribute an OFF issuer only when a matching typed
command receipt establishes it; classify sensor timing as correlation and
bridge output as reporting provenance.
