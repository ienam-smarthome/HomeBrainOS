# Hubitat MCP AI 0.16.63

## Broader performance evidence, same grounding discipline

- Broad performance-and-recommendation requests now instruct the model to read a bounded recent log window after metrics and ranked performance statistics, so live failure patterns can be surfaced without promoting correlation into root cause.
- Scheduler/job evidence is required before cadence/job-volume recommendations, and last-activity/history evidence is required before staleness materially drives a recommendation.
- Database-size compatibility now covers both `hub_get_metrics` and `hub_get_performance_stats`; numeric legacy `databaseSizeKB` values are exposed as `databaseSizeMB` without scaling, with raw provenance retained.
- Broad performance answers are instructed to report the explicit database value/unit and avoid qualitative size labels without an evidence-backed threshold.
- Ordered recommendation numbers/titles survive safety localization.
- Unproven event-volume -> hub-overhead claims and state-size -> cache/history/memory interpretations are localized while measured figures are retained where available.
- Cache/history/state-retention tuning is inspection-first unless current-turn configuration or code supports a concrete change.

## Comparison target

This release deliberately pursues the diagnostic breadth seen in richer external analyses while retaining HomeBrain's evidence policy: recent errors/warnings may motivate investigation, but stale activity, timeouts, heap pressure, log latency, and exact tuning changes are not promoted to proven causes without current-turn linking evidence.
