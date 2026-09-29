# Hubitat MCP AI 0.16.64

## Ground broad performance diagnostics from the 0.16.63 live proof

- Broad performance requests that also ask for recommendations now treat a bounded recent `hub_get_logs` read (`since=30m`, `limit=100`) as a **mandatory current-turn evidence step** before final synthesis, rather than advisory diagnostic breadth.
- Performance guidance now explicitly separates scheduler/job observations from CPU/load attribution: a job list can establish returned jobs and cadence, but not material CPU load, hub overhead, or performance drag by itself.
- A `Hypothesis` label no longer makes assertive mechanism wording such as `likely caused by` or `probably due to` acceptable without direct mechanism evidence.
- Scheduler tuning such as increasing/decreasing `sessionTick`, job, tick, polling, or scheduler intervals is inspection-first unless current-turn configuration/implementation evidence establishes that the setting is configurable and the required behaviour is understood.
- Database synthesis keeps the measured MB value but does not invent qualitative `small`/`lean`/`large` labels or infer performance impact without an evidence-backed threshold/attribution.
- `NETWORK_BACKUP_FAILED` remains an actionable alert, but synthesis no longer upgrades it to `most urgent`, `immediate`, or `prevent data loss` language unless current-turn evidence supports that severity and the status of other backup methods.
- Added a focused fail-closed live-performance semantic validator and regressions using the exact failure shapes observed in the 0.16.63 live response.

## Live validation target

Run:

> Analyse my Hubitat performance and recommend improvements.

Expected evidence should include `hub_get_metrics`, `hub_get_performance_stats`, and a bounded `hub_get_logs` read. Scheduler/jobs or history evidence should be added only when the answer materially depends on cadence/job volume or staleness.
