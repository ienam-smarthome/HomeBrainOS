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

Answer the **requested metric first**. If it cannot be established, say
which sources and windows were actually checked and the exact missing
evidence, then mention any distinct contextual measurements under their
proper units and time labels. Do not fabricate graphs, peaks, aggregates,
continuous-state claims or causal workload descriptions from sparse events.

The optional alpha.44 requested-measurement review asks the normal model
to reconsider source sufficiency before finalising time-scoped historical
reads. It is a model decision, not an automatic source request, deterministic
metric mapper, answer rewrite or exception for any specific device.
