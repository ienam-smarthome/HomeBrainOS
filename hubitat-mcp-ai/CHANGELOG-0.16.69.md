# Hubitat MCP AI 0.16.69

## Summary

0.16.69 refines the broad Hubitat performance analyser after the 0.16.68 live proof. It keeps the now-working production API finalization route while improving latency, database-unit consistency, and fail-closed wording quality.

## Changes

- Reuses the original normalized, privacy-redacted `ToolExecutor` payloads for `hub_get_metrics`, `hub_get_performance_stats`, `hub_get_jobs`, and `hub_get_logs` during final synthesis.
- Removes the three duplicate API snapshot re-reads introduced in 0.16.68.
- Preserves the established database compatibility normalization so the affected upstream `databaseSizeKB` numeric value continues to be treated as MB without multiplying or dividing it.
- Keeps one bounded recent-log read (`since=30m`, `limit=100`) when the original reasoning turn did not already obtain logs.
- Neutralizes unsupported causal labels such as `Blocking Potential`, `Scheduling Overhead`, and `Recurring Overhead` when current-turn evidence only establishes measured latency/job activity.
- Recalibrates unsupported `not a bottleneck` conclusions to an evidence-bounded statement.
- Collapses the duplicate fail-closed sentence pattern exposed by the 0.16.68 Halo3000x live proof.
- Retains the false-evidence-denial fallback from 0.16.68.

## Expected live proof

For:

`Analyse my Hubitat performance and recommend improvements.`

expected behavior is:

- measured analysis from current metrics/performance/jobs/log evidence;
- database size rendered in MB using the normalized original payload;
- no duplicate metrics/performance/jobs API snapshot reads;
- normally four tool calls when the original turn reads metrics/performance/jobs and the API adds the required bounded log read;
- no unsupported blocking/CPU-overhead/bottleneck conclusions;
- no duplicated Halo3000x repair sentence;
- materially lower `performance_api_finalize` time than 0.16.68's duplicate-read path.
