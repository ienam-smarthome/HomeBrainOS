# Hubitat MCP AI 0.16.100

## One-time cleanup observability

- Exposes the effective cleanup schedule, next run, last run, last trigger, last result, running state and last error.
- Adds `GET /api/one-time-rule-cleanup` for deterministic status.
- Adds guarded `POST /api/one-time-rule-cleanup/run` to execute the exact same strict cleanup service immediately.
- HomeBrain Web UI now shows cleanup status, next/last run, last deleted/failed counts and per-rule details, plus **Run cleanup now** with a confirmation prompt.
- Scheduler logs now state when it starts, the exact next Hubitat-local run time, when a cleanup begins and the scanned/eligible/deleted/failed result.
- Automatic cleanup safety is unchanged: only exact expired `(One-time YYYY-MM-DD HH:MM)` HomeBrain rules are eligible; soft delete remains `force=false`, `confirm=true`; there is no startup catch-up deletion.

## Why

A live test changed the configured cleanup time to 15:15, but there was no visible proof that the in-process scheduler had loaded that time or run. The previous scheduler kept `next_run`, `last_result` and `last_error` only in memory and exposed none of them. This release makes the effective running schedule directly inspectable and allows safe same-day live proof without creating a separate Hubitat Rule Machine cleanup rule.
