# HomeBrainOS V2 alpha.118 — failed reads are not evidence; model-led source frontier recovery

**15 November 2026. V2 Preview only.** This note contains only fictional fixture identifiers. It does not contain private household receipts.

## Direction and baseline

The permanent Answer Quality Charter and autonomous evidence-first roadmap remain authoritative. Source-real alpha.116 lighting commands proved an improved fast routine-control path, but neither those control cases nor alpha.117 synthetic post-write readback demonstrate broad first-answer reasoning quality. The repository describes 13 golden tasks plus 40 curated cases; aggregate production grounding, useful-first-answer rate and matched-model explanatory gap remain **not_measured**.

The next generic weakness in V2 was observed by inspecting the existing source-review lifecycle: a *failed* current-request read counted as a `fresh_read_attempt`, and so prevented the existing single model-led `FRESH_SOURCE_RECOVERY_PROMPT` from activating. The final text-audit stage could also trigger after read attempts that produced zero successful observation receipts. A failed native history read is not an empty event history, a negative causal result, or sufficient evidence of source coverage.

## Implemented V2-only model-independent evidence frontier

- `current_source_progress` indexes **original current-request** read-only tool receipts, excluding catalog/clock/prior-context and pre-execution contract failures. It differentiates executed attempts, successes, failures, and distinct successful tool+argument request scopes. It also rejects native domain-level `success:false`/explicit `error` wrapped in a transport-successful MCP result. The scope count is only a request progress metric: it does **not** claim historical coverage, target identity, nonempty observations, physical execution or sufficient evidence.
- The existing model-led read-only source-review round can now offer a fresh-source recovery choice when **zero current observation reads actually succeeded**, *even when the model already attempted a failed native read*. It does not choose, order or dispatch any read: the AI selects from the same live read-only MCP tool catalog. New prompt text explicitly distinguishes a failed/timed-out source from zero returned events and respects user instructions explicitly prohibiting further reads.
- The optional final claim-audit stage is skipped when its fresh-source recovery did not obtain a successful observation receipt. This prevents an additional paid model round that cannot validate new facts. If a read succeeds, existing evidence review and final audit continue unchanged. Existing read-only/write guards, source timestamps, budgets and cancellation remain authoritative.
- PRIVATE Technical JSON includes `current_read_source_progress` counts and explicit limitations. No raw arguments, private labels or device history are copied into that summary; original source receipts remain available separately. Failed source responses are **not** proof of no events.
- The alpha.117 bounded readback, one-round low-risk control, single-use Ask authorisation, heating/lock/network write confirmations, native Rule Machine controls and V1 are untouched. No mandatory historian call, added polling or background processes.

## Offline acceptance and next live acceptance

Fictional tests check mixed success/failure, duplicate identical reads, catalog versus actual execution, native embedded domain errors, explicit no-read instructions, one model-led alternative source chosen after a failed event-history query, and no redundant final AI audit when no read succeeded. This CI is a **source-progress contract regression**, not a Claude-equivalence or factual accuracy score.

**Next installed read-only test:** On alpha.118, ask a new cross-domain causal or historical question without naming specific tools. Capture the original first answer and PRIVATE Technical JSON, showing the tool catalog, source reads, actual return window, error/success scope, source-review decisions, and remaining unknowns. A source failure should not become an absence claim; a model-selected alternative read should be attempted only if available and proportionate. Repeat on a held-out different device type, then begin matched, source-referenced review of the frozen 53-case definitions. Do not fabricate a baseline/p95 or declare >=90% grounding/80% first-answer completeness from CI.
