# HomeBrainOS 0.18.113 — Sensor causal evidence calibration

## Reproduction

The v0.18.112 live test successfully retrieved all 186,457 characters of
Groovy code for installed app 4019 (source ID 1453), read configuration
and sampled logs, but confidently blamed **Livingroom Soft Sensor (7766)**
for ghost occupancy. The exposed typed receipts had no sensor-specific live
motion state and no app log showing that sensor blocked the OFF timer.
Complete source retrieval proves source availability, not execution of
a specific branch. The output also misreported a 20:23–00:41 historical ON
interval as 3h 18m instead of the recorded 15,510 seconds (~4h 19m).

## Changes

- Add a cross-device sensor-blocker claim calibrator operating on the
  final drafted answer and current-request typed receipts, not another
  keyword-based route. Without a matching sensor-specific live state
  **and** an app-log sensor-named OFF blocking decision, replace a
  confident named-sensor diagnosis with a concise **possible cause,
  not verified** summary. Legitimate claims with both receipts survive.
- Distinguish fully retrieved Groovy implementation from proven timer
  execution and selected keep-on sensor membership.
- Correct model-generated ON/OFF duration table values which conflict
  with source-provided `observedIntervals[].durationSeconds`. Allow
  ordinary rounded-minute differences; do not infer full historical
  coverage from a sampled event stream.
- Retain raw technical JSON and highlight calibration decisions under
  `evidence_validation`, not in a new visible completeness paragraph.
- Regression tests use simulated evidence and exercise the actual API
  response builder. No Hubitat writes.

## Remaining investigation

An actual causal verdict still requires verifying controller sensor
membership, the named sensor's historical activity during the affected
ON interval, and the corresponding timer/command decision. This release
reduces unsupported certainty; it does not establish which sensor caused
the observed duration.
