# HomeBrain 0.17.57 — timestamp-aware telemetry and fail-closed causal synthesis

## Source-aware evidence fixes

- Add a timestamped interpretation of device-attributed event histories to
  `investigation_coverage.telemetryTimestampAssessment`. Distinguishes a
  stored `dataAgeSeconds` observation from a fresh age calculation.
- Report the latest *returned* device-attributed state event relative to the
  original Hubitat read receipt's timestamp, without equating a driver
  event to an acknowledged physical/MQTT/Zigbee message.
- Add source qualifications when generated prose claims 24-hour telemetry
  silence despite a device-attributed event within that period. Bounded and
  truncated history remains incomplete, and physical command reachability
  is still unverified.

## Causal safety

- When the model's first answer and its one bounded synthesis repair both
  violate evidence-based causal checks, return a deterministic,
  source-backed event synopsis instead of publishing unresolved,
  contradictory controller attributions.
- The fallback identifies the observed requested ON/OFF boundary, reporting
  source and whether a matching direct command was established in the
  bounded source. It explicitly withholds unsupported automation, sensor,
  physical-controller and empty-log causal conclusions.
- Record `synthesis_causal_fail_closed` as an observable metric; do not
  use an extra model round or issue additional tools at the fallback stage.

## Safety and limitations

No Hubitat mutation. The timestamp assessment supplements an existing
model-produced diagnostic answer; it does not yet fully replace every
unqualified historical claim in that answer. Fail-closed causal synopsis
requires a uniquely identified observed event and falls back to existing
localized corrections if this requirement is not met.

`general_task_engine_enabled` remains disabled by default.
