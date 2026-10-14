# HomeBrain v0.17.58 — evidence-first answers after incomplete investigations

## Changes
- Reconcile the original device telemetry answer against a validated
  historical source-time assessment, not only append a warning below it.
  A stored `dataAgeSeconds` value and truncated event history are no
  longer silently promoted into a fresh clock or absolute telemetry absence.
- Preserve useful source-grounded timing evidence in the fail-closed
  causal fallback. When an answer and repair both fail source verification,
  the fallback reports correctly ordered, focal, observed sensor correlations
  and recorded downstream listeners without naming either as an initiator.
- Cross-entity/source scoping is required: only correlations for the same
  subject, requested event boundary and signed time window are eligible.
- A counter (`telemetry_claims_reconciled`) reports a source-time textual
  correction separately from existing completion and causal fallback counters.
- Add regression tests from the v0.17.57 Bedroom 3 Mesh (device 7103)
  and Livingroom Light 1 (device 7805) live responses.

## Boundaries
- Model-generated telemetry statements are reconciled only for known
  source-time claim classes; this is not a general-purpose semantic proof
  engine, and physical communication remains unverified.
- Sensor proximity/repetition is evidence for a candidate hypothesis,
  never proof that a device/rule actually commanded the light.
- No Hubitat devices, rules or automation settings are changed. The
  general task engine remains opt-in.
