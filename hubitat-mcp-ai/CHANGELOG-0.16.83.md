# 0.16.83 — Format-independent diagnostic evidence gating

## Summary

0.16.83 keeps the accepted 0.16.81/0.16.82 retrieval architecture unchanged and fixes the remaining validator-shape defect exposed by the 0.16.82 live proof.

The live result showed that the structural diagnostic classifier was correct, but the post-synthesis guard only bound a target when the model used numbered bold subheadings. Gemma instead emitted inline bullet diagnostics, so unsupported SenseCap cadence and LG network-latency claims survived. The same run also promoted one observed 16-row same-second cluster into "16 events per second" and treated a threshold-labelled app event as proof that the low-memory condition triggered.

## Format-independent guard

The new `performance_diagnostic_format_guard.py` applies adaptive evidence boundaries by entity and claim type rather than one Markdown layout.

- Inline bullet diagnostics are matched to the current adaptive target by entity name.
- A new labeled bullet resets target context so one scoped target cannot leak into the next unscoped subject.
- `repeated_activity` remains an observed pattern, not a causal mechanism.
- `sparse_or_neutral` and `no_observations` remain explicitly unresolved.
- An unscoped diagnostic outlier cannot receive a mechanism hypothesis merely from performance statistics.
- Mechanism-specific recommendations such as network/driver/polling/timeout changes require supporting target-scoped evidence.

## Timing and event semantics

- Adaptive cadence claims are checked anywhere in the answer, not only inside a `Diagnostic Hypotheses` section.
- If the host did not establish `regular_cadence`, model-authored `every X` / recurring / consistent cadence wording is replaced with the scoped row count and timing limitation.
- A same-second cluster may be described as a bounded cluster, but one observed cluster cannot become a recurring `events per second` rate.
- Same-second clustering is not literal simultaneity.
- A log row whose app name contains `Low Memory <200MB>` and whose payload says `Event: ... freeMemory 917.38` proves that the app processed/logged that event; it does not prove that the `<200MB` condition evaluated true or an alert action fired.

## Architecture unchanged

- Quiet broad-performance case: 3 reads, 0 agent model rounds, 1 synthesis round.
- Strong-outlier adaptive case: at most 5 reads, 0 agent model rounds, 1 synthesis round.
- No new provider planning round.
- No additional diagnostic fan-out.
- Existing 0.16.79/0.16.80 timing classification and 0.16.82 adaptive evidence classification remain authoritative.

## Regression coverage

The exact 0.16.82 live output shape is covered, including:

- SenseCap's unsupported `every 5 to 10 minutes` cadence outside the diagnostic section;
- SenseCap's inline `consistent with` causal wording;
- LG's unscoped network/response-time hypothesis;
- LG's unsupported network-connectivity/driver-settings recommendation;
- one observed `16 events per second` promotion from a 16-row same-second cluster;
- the `Low Memory <200MB>` event row being promoted into a triggered threshold;
- a positive control preserving a real host-established regular cadence.
