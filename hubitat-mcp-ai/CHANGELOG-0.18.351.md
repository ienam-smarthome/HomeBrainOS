# Hubitat MCP AI v0.18.351 — coalesced evidence-first finalization obligations

## Source architecture, not a device-specific prompt patch

Inspection of the current real orchestration code found five possible `self.mcp.list_tools()` schema fetches within one finalization: device logs, target configuration, command history, recorded historical app issuer log, and general method-command issuer log. The latter two planners are independent despite both reading `hub_get_logs` for the issuer of a source-attested device command.

This change makes a narrowly scoped first consolidation:
- One pure, generic `select_issuing_app_log_obligation` combines the existing **historical incident** and **general typed-method** app-log planners. Historical precise incident provenance has priority; otherwise the verified typed-method planner can supply the one obligation. Never fabricate an issuer, target, incident clock or log time window.
- Execute **at most one** issuing-app log request per finalization via the existing `hub_read_diagnostics(hub_get_logs)` source gateway. Preserve live tool schema/effect admission, explicit no-write policy, failed-query no-retry behavior, secrets redaction, and legacy source metrics.
- One **lazy request-finalization scoped capability catalog** is shared by device logs, device configuration, required command history, and the selected app-log plan; no new provider/model/tool round introduced. Avoid repeatedly discovering the same metadata without compromising any source scope.
- Preserve model-authored natural language and all source/uncertainty rules; no host prose replacement. Reconciled device timelines from v0.18.350 remain available unchanged.

## Tests and accepted limits
Anonymous offline tests: single verified typed-method plan, historical incident precedence, unverified issuer excluded, and prior failed log query suppresses retry. Full CI, release metadata, Python suite, and container smoke required at the exact head before merging.

This is an *incremental consolidation*, **not a complete unified planning engine**. We have **not** demonstrated a 45-second investigation or higher natural-answer accuracy. Remaining steps include the bounded pre-model read plan, eliminating overlapping model recovery checkpoints and a frozen source-packet A/B evaluation. **No live Hubitat/HA devices, rules, storage or settings changed.**
