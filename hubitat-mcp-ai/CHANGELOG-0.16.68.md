# Hubitat MCP AI 0.16.68

## Performance final-synthesis context

- Fixes the 0.16.67 live failure where the production finalizer successfully gathered metrics, performance statistics, jobs and recent logs but the second model pass falsely claimed that no MCP tools had run.
- The API performance finalizer now replays the already-selected read-only `hub_get_metrics`, `hub_get_performance_stats`, and `hub_get_jobs` calls into a bounded current-turn synthesis snapshot before the final no-tools model pass.
- Existing bounded `hub_get_logs` evidence is reused through its compact evidence details; a new log read is still performed only when the original turn did not obtain one.
- The final model therefore receives actual measured values instead of only source-presence summaries such as `object fields: ...`.
- The first assistant draft is retained as context but is explicitly not treated as evidence.
- A deterministic contradiction fallback rejects final answers that claim no MCP tools/evidence exist while successful current-turn receipts are present; HomeBrain then returns the original measured draft after the established live-performance semantic guard repairs unsupported database, backup, implementation-causality, scheduler-load, and interval-tuning language.
- Adds API snapshot observability through `performance_api_snapshot_attempt`, `performance_api_snapshot_success`, `performance_api_snapshot_failed`, and `performance_api_false_evidence_fallback` counters.
- Regression coverage reproduces the exact 0.16.67 four-source live-evidence case and requires metrics, performance values, jobs and log observations to be visible to the final synthesis.