# HomeBrainOS V2 alpha.102 — typed original-event answer verification

**Date:** 14 November 2026. **Scope:** V2 Preview only, original user-private MCP receipts excluded from GitHub.

## Source-real problem and independent limitations

An installed alpha.101 answer attempted to enumerate **all returned** ON/OFF events for one light. The same successful unfiltered native `hub_list_device_events` receipt actually contained eight `switch` reports (four observed ON→OFF pairs) and seven command rows, while the model's first draft, source review and final audit all retained six transitions and three pairs, omitted two close-together reports, misordered command/state rows, and used an incorrect requested six-hour window start. It also inferred causal initiators for some state reports despite command rows occurring **after** those state reports.

The original MCP response contained 30 bounded event rows against a 500 limit and an explicit six-hour `sinceTimestamp`. The low row count does **not** guarantee upstream retention completeness. This is a *source-to-answer fidelity* failure, not an independently verified physical event chronology, command cause or outage. Previous reviewer scored the exploratory first answer 3/8. The source-real first answer cannot establish alpha.102 accuracy before this code is tested installed.

## General intervention: source-backed exhaustive projections, not another prompt

For a **narrow explicit question asking for all/every returned historical event/state transitions** with a named state domain (switch ON/OFF, thermostat heating operating state, motion active/inactive, contact open/closed or lock), the **existing final completion boundary** compares the requested scope with original successful native events.

A source-derived ledger replaces a model-authored exhaustive timeline rather than printing unverified lists. The projection enumerates **every** safely parseable matching returned state row, actual offset-aware timestamps in ascending time order and elapsed intervals between adjacent *returned reports*, and all recorded command rows with original command event names and safely identified issuer app IDs. It also reports other returned event-name counts without copying unrelated raw values. Actors who report a state are separated from command issuers; neither alone proves a controller's reason or uninterrupted physical operation. It uses the returned `sinceTimestamp`, not the newest event minus requested lookback.

The ledger is a **typed returned-receipt projection only**: it is not an assertion that the native store returned every event that occurred, nor that every command executed. The model remains responsible for discovering tools and reading the appropriate source, and ordinary causal, exploratory, current-state and write questions stay model-led.

### Fail closed, not fabricate

No exhaustive claim is published from an unsuccessful, contradictory, ambiguous, capped, oversized (more than 120 rows), malformed, multiple-scope or wrong-device native event receipt. If the requested history duration does not match the read, or a user asks for commands but the native read is filtered, the response explicitly states an exhaustive source ledger cannot be verified. Neither failed reads nor absent matching rows prove absent physical events. The filter and returned subset determine the ledger's true scope.

The source ledger includes only enum state values, bounded offset-aware timestamps, safe command event names and short numeric app/device actor IDs. No raw command descriptions, listener arrays, arbitrary attribute values, IP addresses, raw passwords/tokens, logs or private household receipts are replayed into the derived answer. Untrusted source names are restricted; unsupported fields do not produce invented state transitions.

### Costs, safety and observability

No additional model rounds, hub reads, background polling, cloud provider switch, automation approval changes or native writes are introduced. A small local source-projection pass replaces only *explicit exhaustive returned-event* answers when a single original successful source is adequate. The private Technical JSON retains original receipts and model stage trace; `structured_history_verification` records status (`source_ledger_used`, `unverified` or `not_applicable`), safe counts and reason. It does **not** constitute an independent score for the underlying model.

No V1 runtime, test, configuration or UI changes are part of this increment.

## Synthetic acceptance and live validation

Fully synthetic tests cover an eight-vs-six discrepancy and seven command rows, source time windows, command-after-state ordering, other state domains, malicious actor descriptions and sensitive unrelated values, failed/ambiguous/capped/wrong-device receipts, and a scripted already-existing final-audit run that publishes the typed ledger with one read and no new model pass.

Require exact-head full Python, repository validation, V2 pilot/container/UI, release metadata and scorecard CI before merge, then post-merge checks.

**Next source-real acceptance:** after hub stability and Preview alpha.102 update, ask one *new independent* read-only question explicitly requiring all returned state transitions and commands for a device not used in prior scripted benchmarks. Compare the ledger **row-for-row** with the original successful source, including clocks and issuers, returned-window boundary, missing/failed source handling, model rounds/tokens, no writes and latency. Test a non-exhaustive causal question separately to verify the model remains the author of inference, not the ledger. Do not claim improvement solely from synthetic CI.

**Rollback:** revert to alpha.101 if it intercepts unrelated requests, leaks untrusted values, misstates original timestamps, or interferes with source selection/approvals. If independent live evaluation still shows contradictions, stop repeated prompt patches and expand typed evidence schemas with measured coverage rather than targeting named devices.
