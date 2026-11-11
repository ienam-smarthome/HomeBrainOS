# Requested-measurement fidelity (general evidence reference)

For any request for measured usage, readings, trends, peak, average, rate,
duration or history, first identify **the exact requested quantity/attribute,
unit, target, time interval and aggregation**. These are separate constraints,
not interchangeable hints. Match each reported value to all of them.

- Current inventory/state is a snapshot at its own source/retrieval time;
  it is not historical sampling for a preceding night or earlier interval.
- A historical query with zero matching returned rows means zero **returned
  matching samples**, not a measured value of zero, inactivity or proof that
  every recorder lacks data. Respect the actual filter, interval, row limit,
  timestamp precision and coverage.
- Other returned measurements may be useful context but are NOT an automatic
  substitute. For example, power (watts) is not cumulative energy (kWh);
  electrical current (amperes) is not true AC power without suitable voltage
  and power-factor information. Similarly, a battery percentage is not charge
  power, and a current temperature is not the previous day's temperature.
- A mathematically valid conversion or derived interval average may be
  reported **as a derived estimate**, with explicit input readings, units,
  elapsed time, temporal coverage and assumptions; do not label it a direct
  historical sensor measurement or a peak when the evidence supports only
  an average. A tiny cumulative change does not establish a complete load
  profile, precise activity window or what a computer/device was doing.
- When useful historical data may be available in another *actually
  connected* permitted read-only source, let the model choose whether to
  inspect it. Do not imply Home Assistant, a device's native telemetry or
  another recorder was checked merely because it might exist.

The requested historical measurement takes precedence over related proxy
measurements. Answer the **requested metric first**. If it cannot be established, say
which sources and windows were actually checked and the exact missing
evidence, then mention any distinct contextual measurements under their
proper units and time labels. Do not fabricate graphs, peaks, aggregates,
continuous-state claims or causal workload descriptions from sparse events.

The optional alpha.44 requested-measurement review asks the normal model
to reconsider source sufficiency before finalising time-scoped historical
reads. It is a model decision, not an automatic source request, deterministic
metric mapper, answer rewrite or exception for any specific device.


## Structured monitor history provenance (alpha.48)

The optional saved-device-history tool now returns SOURCE-DERIVED extrema and
coverage for the **exact returned interval** in `summary`; its `range=12h`
produces a 12-hour upstream custom read, rather than reusing 24h totals.
For `range=custom` supply BOTH `start` and `end` offset-aware timestamps.
For multiple devices, prefer the same explicit custom start/end.

- `saved_bin_extrema` covers all non-null saved bins, regardless of whether
  they contain new reports. For power, `report_containing_saved_bin_extrema`
  and the legacy highest/lowest report-containing extrema cover only bins
  with powerReports > 0. These are **saved-bin extrema**, never proven
  continuous physical peaks or precise device-source report timestamps.
- `expected_bin_positions` means *bin starts in the half-open interval*
  [window_start_utc, window_end_exclusive_utc). `all_expected_bin_positions_populated`
  means each expected slot has a saved value, **not** that the device was
  continuously observed. `coverage_complete` remains false.
- `explicit_null_bin_rows` means upstream rows with no valid measurement;
  `absent_bin_positions` means time positions with no returned row;
  `missing_bin_positions_total` counts both kinds of unavailable saved
  values in the expected grid. These must NOT be conflated with a valid
  `held_from_report` power bin, which has a carried-forward value but no
  newly reported power value in that bin.
- For **temperature, humidity, setpoints and level**, the source does not
  encode per-bin sensor report freshness. `sample_class =
  sensor_freshness_unverified` and `sensor_freshness_known_from_source =
  false` mean the bin **may** be fresh or cached; do not claim all such
  bins were stale or all were fresh. Report saved-bin extrema and the
  limits of the source.
- Do not promote a 24-hour extrema/gap summary into a 12-hour comparison.
  Compare the actual per-device source-window boundaries and reported
  resolutions; source reports fetched separately may use slightly different
  relative end times. Report differences as observational patterns, not
  demonstrated appliance operating causes.


## Shared historical comparisons (alpha.49)

For multiple selected devices and the same quantity, the optional monitor
tool supports `mode=compare` with 2–5 distinct `device_ids`, a `metric`
and relative `range` 1h/6h/12h/24h or `range=custom` plus BOTH offset-aware
`start`/`end`. The MODEL chooses whether a grouped read is useful; there
is no automatic sequence, forced tool call or device action. Source status can
discover monitored IDs. The comparison returns only compact per-device
source-derived histories; for original full saved-bin samples use the
independent `mode=history` query.

The comparison pins one captured UTC interval for every device.
Relative requests end at the last complete five-minute boundary, not
necessarily the current second; the result reports the clock capture and
boundary alignment. Custom intervals preserve user-provided boundaries
and may contain partial edge bins. Inspect both each device's requested
interval and the upstream returned interval before stating coverage.

`summary.missing_runs` reports consecutive bin-position spans without a
non-null saved value; `summary.held_value_runs` reports consecutive power
bins with carried-forward values. Use `count`, `longest` and bounded
`runs_preview`, and disclose truncation. These spans are NOT observed
physical-off durations, measured zeros, reporting outages or proof the
underlying source stopped. Do not equate an empty TV power archive in the
requested interval with the TV being off.

If comparing different sensors, identify per-bin freshness as unknown
unless the returned source explicitly authenticates fresh reports.
Never claim uninterrupted source data from a complete saved-value grid.

## Source-neutral historical source choice (alpha.52)

For a historical quantity, choose suitable read-only sources by actual
returned interval and measurement provenance. Users do **not** have to
name Hub & Device Monitor for the model to consider its configured
archived readings. Native Hubitat device-event history is a separate,
sometimes narrower source: a successful attribute-filtered query whose
oldest returned event is hours after the requested start cannot establish
a whole-interval maximum or that a threshold was never exceeded. That
fact does not establish why older events were absent.

If an earlier SERVER-HELD receipt index reports source-derived saved-bin
extrema for an overlapping interval, treat it as earlier source data,
not a fresh reading. Inspect the original receipt in chunks or re-read
the relevant source to reconcile a contrary native event excerpt. Never
silently prefer the latest read simply because it is newer. Compare
returned windows, filters, aggregation and freshness semantics. A saved
humidity value may have been held; a sharp rise cannot by itself prove
a shower, particular activity or exact continuous duration. Distinguish
strictly greater than from greater-than-or-equal thresholds and do not
promote bin starts to proven physical crossing times.

This is source-adequacy guidance. The connected model still chooses
the tools and when to stop; there is no fixed sequence, mandatory
monitor call, device-specific exception or post-hoc answer rewrite.
