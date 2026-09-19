# Hubitat MCP AI 0.14.0

## Scheduled morning system health and dashboard audit

0.14.0 adds a deterministic operational-health layer so HomeBrain can check the
Hubitat/MCP environment every morning and expose the same check manually from the
dashboard.

This feature is intentionally separate from the general AI reasoning loop. The
health audit is read-only, repeatable, persisted, and testable.

## HealthAuditService

New runtime module:

- `health_audit_service.py`

Each audit checks:

### Hub / MCP

- MCP reachability;
- installed MCP tool count;
- Hub Info device metadata when available;
- firmware/update status;
- uptime, free memory, CPU/temperature/database fields when the Hub Info driver
  exposes them.

Hub/MCP unavailability is a critical finding.

### Devices

The audit refreshes the detailed Hubitat device manifest and records:

- total devices checked;
- devices that explicitly report offline/unavailable/dead/disconnected or
  reachable/online=false;
- batteries at or below the configured threshold.

Only explicit health/connectivity attributes are used for offline classification.
A normal presence value such as "not present" is not treated as an offline device.

### Automations

The audit reuses the existing `AutomationStatusService` normalization.

Attention statuses:

- broken;
- paused;
- unknown.

Disabled automations are counted and visible but are not automatically treated as
faults because many intentionally disabled rules are valid configuration.

### Logs

When `hub_read_diagnostics` is installed, the audit calls the native
`hub_get_logs` operation for the configured lookback period.

Both supported MCP gateway envelope shapes are handled from the live tool schema.

Structured log rows are grouped into recurring warning/error signatures so repeated
copies of the same warning become one finding with an occurrence count rather than
flooding the morning report.

A missing or failed diagnostics/log source is itself reported as an audit gap.

## Stored snapshots and change tracking

The latest audit and previous audit are persisted atomically at:

`/data/homebrain-health-audit.json`

The current result includes:

- overall status: `healthy`, `attention`, or `critical`;
- attention/info severity counts;
- new findings since the previous audit;
- resolved findings since the previous audit;
- detailed Hub, device, automation, MCP, and log sections;
- audit duration and configured thresholds.

The dashboard reads this stored snapshot rather than rerunning an expensive audit
every time the page loads.

## MorningHealthScheduler

New runtime module:

- `health_audit_scheduler.py`

The scheduler:

- runs once per day at the configured time;
- resolves the Hubitat timezone for local scheduling;
- starts after a short boot delay;
- supports a one-hour catch-up window after add-on restart;
- never runs the same scheduled audit twice for the same local day;
- records the next scheduled run and scheduler error state for the UI; and
- is cancelled before MCP shutdown.

An invalid configured clock time falls back safely to 07:00 instead of preventing
the add-on from starting.

## Dashboard

The ingress dashboard now contains a dedicated **System Health** card showing:

- current health message;
- items needing attention;
- new findings;
- resolved findings;
- number of devices checked;
- last audit time;
- daily schedule / next run;
- expandable current findings.

A **Run system check now** button invokes the same deterministic service used by the
scheduler.

New endpoints:

- `GET /api/health-audit` — read the stored result and schedule status;
- `POST /api/health-audit/run` — run the audit immediately.

## Configuration

New add-on options:

- `morning_health_check_enabled: true`
- `morning_health_check_time: "07:00"`
- `health_check_log_hours: 24`
- `health_check_low_battery: 20`

## Safety

The audit is read-only.

It does not:

- reboot the hub;
- install firmware;
- enable/disable/pause/resume automations;
- control devices;
- clear logs; or
- repair a finding automatically.

Corrective actions remain separate explicit user requests and retain the existing
confirmation/mutation policies.

## Regression coverage

0.14.0 adds tests for:

- low-battery and explicit-offline device classification;
- automation attention vs intentionally disabled status;
- grouped recurring log warnings/errors;
- direct and nested diagnostics gateway argument shapes;
- persisted latest/previous snapshots;
- new/resolved issue tracking;
- morning time parsing and next-run calculation;
- catch-up behavior;
- invalid schedule fallback;
- health-audit API endpoints; and
- dashboard System Health controls.
