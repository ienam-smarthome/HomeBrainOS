# HomeBrain 0.17.25 — Opt-in persistent historical evidence journal

- Introduces an experimental, **disabled-by-default** read-only live-socket collector using Hubitat LAN `/eventsocket`; optional allowlisted app-log collection uses `/logsocket`. No hub commands or background polling are issued.
- Captures selected lighting, occupancy/motion and button attributes into SQLite under persistent HA add-on `/data`. Defaults: 30 days and at most 100,000 rows; storage cleanup occurs on startup and periodically during writes.
- Tracks connected streams, collector-reception timestamps, dropped rows and explicit connection outage ranges. A missing journal row does **not** prove device inactivity or an automation's non-execution.
- Captures only explicitly allowlisted app IDs when app-log collection is additionally enabled. Rejects URL credentials and public Internet destinations.
- Adds read-only `/api/evidence-journal/status` and narrowly scoped `/api/evidence-journal/events` endpoints.
- Secondary focal OFF investigation can consult the optional journal for up to two known room-local sensors; those observations are deliberately **separate from verified MCP events** and cannot independently prove a command or exact event timestamp.
- Source-time/collector-receive distinction, retention, startup persistence, write batching, gap handling, and restricted log collection are covered by regression tests.
- Requires explicit add-on configuration and a restart. Historical gaps before enablement cannot be recovered. The Hubitat sockets are unofficial and could change across firmware releases.
