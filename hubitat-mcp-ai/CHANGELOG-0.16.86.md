# 0.16.86 — Use adaptive performance evidence directly

## Summary

0.16.86 keeps the accepted performance retrieval/model architecture unchanged and fixes the evidence-use defects exposed by the 0.16.85 live proof.

The live run showed two distinct issues. First, Google Nest Hub scoped logs contained repeated WARN-level `runQ` durations from roughly 129 seconds through more than 400 seconds, but the diagnostic classifier called the 72-row receipt non-diagnostic because comma-formatted millisecond values such as `166,621ms` were not matched. Second, the adaptive app read used `appId=3919` while the final prose highlighted SenseCap ID 4129; review of the host selector showed that this is not sufficient evidence of a wrong-ID bug because adaptive selection uses independent busy/total/average thresholds. The correct fix is to carry the exact triggering performance row into the adaptive receipt rather than infer target identity from final prose.

## Adaptive target provenance

Every adaptive diagnostic receipt now carries `details.adaptiveTarget` with:

- target kind, ID and name;
- `selectionSource=hub_get_performance_stats`;
- whether the target was re-found as the exact same ID+name row;
- the selected row's measured `pctBusy`, `pctTotal`, `averageMs`, count, state size and total runtime fields when present.

This provenance survives even when the scoped log read returns zero rows. No re-resolution or name/ID substitution is needed later.

## Long-running Hubitat WARNs

The diagnostic classifier now recognizes explicit duration language such as `ran for 166,621ms`, including comma separators. Retained long operations >=5 seconds classify the scoped receipt as `diagnostic_signal`; WARN/ERROR long calls are counted separately and min/max retained durations are exposed to deterministic synthesis.

Long-running-operation evidence and connectivity evidence are kept distinct:

- explicit timeout / HTTP 408 / no-route / unreachable signals may support a calibrated connectivity/failure hypothesis;
- repeated very-long method-duration WARNs may support a calibrated stalled/excessively-long-running-operation hypothesis;
- neither proves worker-thread blocking, the exact driver implementation cause, a network cause, or user-visible delay without stronger evidence.

## Literal WARN preservation

WARN/ERROR restoration now matches final prose by structured source identity as well as the raw `app|id|name` token. A model line such as `MCP Rule Server (ID 4151)` can therefore be matched safely to the current-turn `app|4151|MCP Rule Server` warning.

The literal log-observation guard also runs as the final performance-validation pass, so a concrete `slow internal GET` warning cannot be replaced again by later generic `returned activity` prose.

## Same-second cluster recommendations

Host-derived same-second cluster evidence remains observational. Without integration configuration evidence, recommendations are inspection-first: review whether grouped updates are expected/configurable. The final log-evidence pass removes prescriptions to stagger, offset, spread, or change reporting frequency when the current turn has not established that such tuning is configurable, necessary, behavior-preserving, or performance-improving.

## Architecture unchanged

- Quiet broad-performance case: 3 reads / 0 agent model rounds / 1 synthesis round.
- Strong-outlier adaptive case: at most 5 reads / 0 agent model rounds / 1 synthesis round.
- No new Hubitat source.
- No additional provider round.
- No change to adaptive retrieval thresholds.
- No change to host-derived timing arithmetic or packet budgets.

## Regression coverage

0.16.86 tests cover:

- comma-formatted Nest `runQ ... ran for Nms` WARNs becoming `diagnostic_signal` with retained min/max durations;
- long-running-operation hypotheses remaining distinct from network/connectivity hypotheses;
- exact adaptive-target provenance when the selected app returns zero log rows, including a case where SenseCap is below adaptive thresholds and another app legitimately wins on `averageMs`;
- MCP Rule Server literal `slow internal GET` warning restoration from a final line that names the app by name + ID rather than raw source token;
- inspection-first handling of same-second cluster recommendations instead of unsupported staggering/frequency prescriptions.
