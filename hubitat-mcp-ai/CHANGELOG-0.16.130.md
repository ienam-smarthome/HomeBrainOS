# HomeBrainOS 0.16.130 — whole-hub optimisation intent and presentation

## Fixed
- Recognize broad requests to review **all devices, rules, apps, logs and automation activity to optimise hub efficiency**. These now use the evidence-driven performance planner ahead of the generic health-only audit.
- Include scheduled-job reads automatically for whole-hub optimisation intent, even if the prompt does not explicitly say "jobs" or "polling".
- Prevent semantic diagnostics from breaking Markdown tables: interleaved caveats are moved after the ranked recommendations rather than being dropped or accidentally tied to the nearest row.
- Add evidence-specific synthesis guidance: errors from failed `hub_get_app_config` lookups can come from external diagnostic requests. They do **not** establish permanent stale dependencies inside the MCP Rule Server; an invalid filter/source parameter is a separate caller-argument error. Actual code/config must be read before recommending cleanup.
- Warn about capped log samples and maintain distinction between `pctBusy`, `pctTotal`, and CPU load.
- Regress exact user prompt and representative badly formatted answer from v0.16.129.

## Known limitations
- Scheduler summaries may be based on a truncated tool result and are not a complete per-app efficiency ranking. Issue #733 tracks authoritative per-app scheduled-job aggregation and event/state coverage.
- No Hubitat devices, apps or automations were changed. Any optimization requiring a write needs a separately confirmed action.
