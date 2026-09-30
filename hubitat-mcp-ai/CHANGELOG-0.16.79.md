# Hubitat MCP AI 0.16.79

## Host-derived log timing precision

0.16.79 keeps the 0.16.78 host-planned **3-tool / 1-model-round** broad-performance path unchanged. It fixes the remaining factual-precision defect exposed by the 0.16.78 live proof: the model described two `CumulativeEnergyImported` observations one minute apart as an approximately 30-second cadence.

The existing log evidence compactor already scans the full bounded log result while retaining only a small raw excerpt in the evidence receipt. It now derives structured timing facts during that same pass:

- per-source/per-signal observation counts;
- median/min/max observed intervals;
- a regular-cadence value only when at least two intervals agree within a bounded tolerance;
- a single observed gap when only two timestamps exist, rather than promoting one gap into a cadence;
- same-second clusters with row count, distinct source count, and measured millisecond span.

No new Hubitat read and no new provider round are introduced.

## Deterministic timing backstop

`performance_log_observation_guard` now checks model-authored log timing claims against those host-derived facts. A cadence claim is corrected only when the same source/device and signal are identifiable in the answer. If the host has only two observations, the guard describes the observed gap instead of inventing a recurring cadence.

When a host-derived same-second cluster exists, wording such as `simultaneously at 08:47:03` is localized to `within the same reported second at 08:47:03`; the evidence does not claim truly simultaneous execution.

## Regression proof

The 0.16.78 live timestamps are represented directly in the new regression fixture:

- Halo3000x `ActivePower`: approximately 10-second cadence;
- Halo3000x `CumulativeEnergyImported`: approximately 60-second cadence;
- four Octopus sources inside `08:47:03`, spanning 40 ms;
- two-point timing samples remain an observed gap, not a cadence.

## Architecture

The accepted 0.16.78 path remains the target:

- host-planned metrics + performance stats + bounded recent logs;
- normally 3 Hubitat tool calls;
- 0 agent planning model rounds;
- 1 evidence-first performance synthesis round;
- scheduler/job evidence only when explicitly requested.
