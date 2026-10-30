# v0.18.260 — Repeated input reception patterns without inventing causal chronology

## Confirmed limitation from v0.18.259
The historical input fallback worked. It returned 160 archived motion observations for independently scoped device 7754 (query truncated), and 10 archived motion observations for input device 7895. All were **collector reception-only**, not native event timestamps. Existing logic correctly refused to treat them as source-clock observations, but then discarded their repeated co-occurrence patterns entirely. In addition, the request-scoped EvidenceRecorder safely caps each nested observation array at 20 rows, which hid 140 of the returned observations from final synthesis for the noisy sensor.

## Shared evidence contract improvement
- A separate **reception-only co-occurrence** tier compares safely retained input reception times against independently source-timestamped switch boundaries. This is explicitly not a verified relative event order, original input clock, historical execution proof, or causal initiating command.
- The original model receives bounded evidence indicating how many target ON boundaries had a nearby active reception (±3 s), and how many OFF boundaries followed an inactive reception within 20 s. The comparison is scoped to one independently verified target ID to avoid counting two synchronised lights as two independent replications.
- Archive recovery now computes the same compact receipt-safe pattern from **all returned observations, before EvidenceRecorder's 20-entry array cap**. Its summary includes signed reception deltas, retrieved vs exposed row counts, truncated-query warnings and explicit `crossClockOrderVerified=false` and `causalInitiatorVerified=false`. The original shared evidence collector and final digest can use that full-page summary without injecting a separate causal reasoning agent or unbounded token payloads.
- Source-timed inputs remain a different tier, and collector-only events never enter `independent_input_observations`.
- Final narrative can now report repeated **tentative associations** rather than claiming no related sensor evidence exists. It must still state that transport latency, journal gaps and unknown source execution prevent attribution of the initiating controller.
- No app/device writes, source permission changes, unscoped sensor searches, background collectors, or new MCP tools.

## Tests
New generic regressions simulate repeated source-timed transitions, a noisy archived input response larger than 20 rows, safe receipt truncation, read-only source validation, preservation of the full-page correlation count, and explicit rejection of source-timestamp and causality proof. All repository CI required before merge.

## Known limits
A high co-occurrence count can arise from shared environmental conditions, common upstream automations or independent transport delays. It is not a direct relationship proof. Historical Journal remains truncated whenever its query indicates additional unreturned rows, and no complete sensor history is claimed.
