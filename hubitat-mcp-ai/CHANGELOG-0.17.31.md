# HomeBrain 0.17.31 — Request metrics registry hotfix

## Root cause

HomeBrain 0.17.30 correctly entered focal OFF app-log reconciliation, but the new call
`increment_active_metric("causal_archived_app_log_checks")` was not included in
`RequestMetrics.ALLOWED_COUNTERS`. During a real request, RequestMetrics raises
`ValueError: Unsupported metric counter: causal_archived_app_log_checks`, which
aborts the investigation and returns an error response. This is a runtime metrics
allowlist problem, **not a Historical Journal database failure**.

## Fix

- Register `causal_archived_app_log_checks` to preserve the intended telemetry.
- Also register `causal_broad_inventory_blocked`, another literal counter in
  the orchestrator that was absent from the registry and could fail on its own
  less-common path.
- New CI regression walks all Python files in the installed application
  source tree, checking all literal `increment_active_metric`,
  `observe_active_metric_max` and `add_active_metric_ms` keys against the
  privacy-safe metric allowlists. Unknown dynamic or private metric names
  remain rejected.
- Regression exercises both counters with an active request context and
  validates recorded counts.

No changes to Hubitat devices, commands, automations, journal records, capture
rates or your 7-day / 200,000-row Historical Journal configuration.

## Live verification

Update to 0.17.31 and repeat the Bedroom 1 Light OFF question about
approximately 17:14:05 on 12 October 2026. The request should complete
without an unsupported-metric error. Check `journalFirstPlan` and
`archivedAppLogReconciliation` in technical details. The initiating OFF
cause may still be unverified without matching command or execution evidence.
