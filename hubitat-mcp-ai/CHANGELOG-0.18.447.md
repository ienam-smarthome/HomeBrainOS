# HomeBrainOS v0.18.447 — Source history span clarity

## Why

A source-real read-only Bedroom 1 TRV request on installed v0.18.446
retrieved **204 raw device events over five pages** with 11 matching
temperature observations between 20:30:52 and 00:06:35 GMT (3h36m).
The model correctly calculated 22.0°C → 22.2°C (+0.2°C), but its history
caveat misleadingly said "only ~3h36 of history were retrieved."
That 3h36m was the *matching temperature sample span*, not the span
of all fetched raw device events. The 24-hour requested lookback was not
independently proved complete; source retention remained unverified.

## Reusable change

- The existing read-only device-history adapter now exposes two independent
  spans: `sampleBounds.spanSeconds` and `sourceEventRange.spanSeconds`
  with distinct earliest/latest timestamps. It also reports
  `sampleBounds.timestampedCount`.
- A deterministic `sourceCoverageNarrative` reports the number of raw
  fetched event rows, selected attribute observations, pages, both time spans,
  whether the requested boundary was reached, the stop reason and explicit
  uncertainty about total source retention. It never calls the raw rows
  "all retained events" or the sample span "only N hours of history."
- Technical JSON evidence details retain the narrative and raw source range,
  alongside existing `sourceEventCount`, `sourcePagesFetched`,
  `sourceCoverageStopReason` and `historySourceIntegrityVerified`.
- A generic model presentation policy distinguishes requested lookback,
  fetched raw-event time range and matching-attribute observation range.
- No inferred duration from fewer than two parseable observations: the
  sample span is `null`, not misleading zero seconds.
- No new MCP operations, read calls, write permissions, resource ceilings,
  cloud routing or Hubitat mutations. The source-real timestamp and pagination
  behaviour introduced in v0.18.446 remains unchanged.

## Verification and limitations

Run CI and synthetic regression tests with mixed-device raw history, sparse
attribute matches, zero/single samples, evidence projection and no-coverage
claims. The semantic correction is at the source/proof/prompt layer; do not
claim a measured natural-language improvement without another held-out
source-real request. The same existing uncertainties remain: Hubitat's
independent retention completeness, source reliability and general first
answer performance are not proven.

## Next acceptance gate

After update to v0.18.447, ask a source-neutral history question and inspect
the full Technical JSON for correctly separated raw and matching observation
ranges. Then run the previously defined, read-only multi-source incident test
for the most recent Livingroom Light 2 OFF event. The test must distinguish
reported OFF state, command producer, app log triggers, and possible causal
alternatives without claiming an unverified definite cause.
