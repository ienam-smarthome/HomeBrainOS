# 0.16.85 — Consolidated performance presentation integrity

## Summary

0.16.85 keeps the accepted performance retrieval and adaptive diagnostic architecture unchanged and fixes the final presentation-integrity defects exposed by the 0.16.84 live proof.

The 0.16.84 run proved that the host still used the intended five-read adaptive path with zero exploratory agent model rounds and one final synthesis round, but the answer could still lose scoped-target context when the model used labels such as `Confirmed Finding` or `Diagnostic Evidence`. It could then falsely state that no target-scoped evidence was read even though the request contained successful six-hour Nest and SenseCap diagnostic reads. The same run also showed a source/timing integrity failure where the `CumulativeEnergyImported` identity was attached to `ActivePower` interval statistics.

## Consolidated diagnostic field roles

Child diagnostic fields are now recognized by semantic role rather than exact strings. Variants such as:

- `Finding`, `Confirmed Finding`, `Diagnostic Finding`
- `Evidence`, `Diagnostic Evidence`, `Observed Evidence`
- `Conclusion`
- `Hypothesis`, `Diagnostic Hypothesis`
- `Verification`
- `Action`, `Recommended Action`, `Next step`

inherit the current diagnostic target unless they explicitly name another target. A wording change by the model therefore cannot erase a successful scoped investigation.

If a target-scoped read exists, a statement such as `No target-scoped diagnostic evidence was read` is repaired using that target's actual classified evidence. Repeated neutral Nest volume observations remain evidence-bounded and unresolved as a mechanism. SenseCap HTTP 408 / connection-timeout evidence remains available as a real `diagnostic_signal` and may support a calibrated failure/connectivity hypothesis while preserving the boundary that the exact implementation mechanism and contribution to longer-window busy percentages are unproven.

## Atomic host timing

Timing presentation is now atomic. Source, signal, timing kind and interval numbers are rendered from one host-derived timing record rather than combining a model-authored timing description with a separately injected source name.

This prevents a result such as:

`CumulativeEnergyImported — median 10.001s, range 9.93–20.013s`

when those numbers actually belong to `ActivePower`.

For the exact 0.16.84 host evidence, the deterministic output is now bounded to the correct facts:

- `Halo3000x socket power ActivePower` — irregular intervals, median 10.001s, range 9.93–20.013s.
- `Halo3000x socket power CumulativeEnergyImported` — regular cadence, median 60.002s, approximately every 60s, range 60.001–60.004s.

## Validator consolidation

The older numbered-heading diagnostic guard is no longer chained after the newer format-independent guard. One consolidated validator now owns:

- entity context;
- semantic child roles;
- adaptive evidence classification;
- source/signal timing integrity;
- same-second cluster boundaries;
- threshold-event wording;
- mechanism-specific action gating.

This removes a second shape-dependent rewrite pass that could contradict an already-correct evidence repair.

## Architecture unchanged

- Quiet broad-performance case: 3 reads / 0 agent model rounds / 1 synthesis round.
- Strong-outlier adaptive case: maximum 5 reads / 0 agent model rounds / 1 synthesis round.
- No additional Hubitat calls.
- No additional provider planning round.
- No broader diagnostic fan-out.

## Regression coverage

The 0.16.85 suite directly covers the 0.16.84 live failure shape and asserts that:

- scoped Nest evidence can no longer become `no target-scoped evidence`;
- SenseCap's explicit HTTP 408 and timeout observations remain visible and useful;
- a diagnostic-signal hypothesis is calibrated rather than promoted into proof of performance causality;
- an already-scoped target is not told to collect target-scoped evidence again;
- `Confirmed Finding`, `Diagnostic Evidence`, `Observed Evidence` and `Diagnostic Hypothesis` preserve target context;
- timing source/signal and timing numbers are rebuilt from the same host record;
- the `CumulativeEnergyImported` line cannot inherit `ActivePower`'s 10-second statistics;
- the consolidated `validate_synthesis()` path applies the single format-independent diagnostic guard.