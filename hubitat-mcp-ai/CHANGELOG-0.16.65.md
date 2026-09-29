# Hubitat MCP AI 0.16.65

## Performance evidence finalization

- Performance semantic validation now activates from `hub_get_performance_stats` evidence alone; a failed or rejected log read can no longer bypass the fail-closed semantic guard.
- Broad performance + recommendation requests host-enforce one bounded recent log read (`since=30m`, `limit=100`) before final synthesis.
- Host finalization tries `hub_manage_logs/hub_get_logs` first and one `hub_read_diagnostics` fallback; if both fail, the answer must state that the log review is incomplete.
- Split database wording such as `Database: Lean. At 168MB...` is localized so qualitative size/performance conclusions do not survive without a defined threshold.
- Exact regressions cover the 0.16.64 live failures: assertive LG mechanism hypotheses, scheduler-to-CPU attribution, unverified `sessionTick` interval tuning, qualitative database claims, and over-severe backup wording.
- New privacy-safe counters expose host log attempt, success, retry, unavailable, and failure outcomes.
