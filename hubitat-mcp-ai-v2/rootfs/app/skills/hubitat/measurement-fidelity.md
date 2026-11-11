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
