# Hubitat MCP AI 0.16.81

## Adaptive performance diagnostics

0.16.81 keeps the accepted 0.16.78-0.16.80 host-planned baseline performance path and adds a bounded diagnostic expansion only when returned performance rows cross internal retrieval-policy thresholds.

### Baseline remains fast

A normal broad performance+recommendation request still reads:

1. `hub_get_metrics`
2. `hub_get_performance_stats`
3. one bounded `hub_get_logs` window (`30m`, max `100` rows)

`hub_get_jobs` remains conditional on an explicit scheduler/job objective. No exploratory provider/model round is added.

### Bounded adaptive expansion

After the baseline performance-stat read, the host may select at most:

- one device target, and
- one app target.

Selection uses only numeric execution measurements as a retrieval-cost decision. The thresholds are not health/severity classifications and must never be presented to the user as such.

Each selected target receives one server-side scoped `hub_get_logs` read:

- `deviceId` or `appId`
- `since: 6h`
- `limit: 120`

Therefore the ordinary case remains three reads; a fully expanded case is capped at five reads. The final evidence-first synthesis remains one model round.

### Diagnostic hypotheses without unsupported causality

Scoped adaptive log excerpts are carried into the final synthesis contract without replacing the existing baseline log packet. The final model is instructed to separate:

1. Confirmed finding
2. Diagnostic evidence
3. Diagnostic hypothesis
4. What remains unproven / verification step
5. Inspection-first action

A hypothesis must be explicitly calibrated (`consistent with`, `suggests`, `possible`) and supported by multiple current-turn observations. Timeout/error/very-long-call evidence may support a connectivity or stalled-I/O hypothesis, but it does not by itself prove worker-thread blocking, the exact driver defect, or user-visible delay.

Exact setting/code changes still require current-turn configuration or implementation evidence.

### Observability

New privacy-safe counters show when the adaptive stage ran, how many reads were added, whether a device/app target was selected, and whether a scoped diagnostic read failed. Device/app names and IDs are not used as metric dimensions.

### Regression coverage

The 0.16.80 live-shaped case proves:

- Google Nest Hub is selected ahead of a lower-busy LG TV average-time outlier.
- Google Calendar Notifier is selected ahead of an average-time-only Device Health Monitor outlier.
- The expanded case performs exactly five host reads and zero pre-synthesis model-planning rounds.
- A quiet performance case remains exactly three host reads.
- Scoped `runQ` / `setVolume` evidence reaches final synthesis as diagnostic evidence with explicit hypothesis/verification boundaries.
