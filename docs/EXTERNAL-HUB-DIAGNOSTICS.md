# HomeBrainOS external Hubitat diagnostics (opt-in)

HomeBrainOS runs in Home Assistant, outside Hubitat's JVM, so resource
observations survive a Hubitat freeze or reboot.

This is an evidence collector, NOT a memory-failure diagnosis, and it
never issues Hubitat reboot or device commands.

## Install / enable

Requires HomeBrainOS version **0.18.421 or later** with the external
diagnostics options. Open:

Home Assistant → Settings → Add-ons → Hubitat MCP AI → Configuration.

If the new options are absent, update the HomeBrainOS add-on from its
repository; merely changing the old add-on settings will not install
the recorder. Enable:

- external_hub_diagnostics_enabled = true
- external_hub_diagnostics_hub_url = http://192.168.1.239
- external_hub_diagnostics_probe_seconds = 30
- external_hub_diagnostics_retention_days = 30

The recorder accepts only a literal private RFC1918 IPv4 address on
port 80 or 8080, with no credentials, external host, path or query.
It does not require a Hubitat MCP token.

For relevant app errors and connection gaps, also enable HomeBrain's
existing Historical Evidence Journal:

- historical_journal_enabled = true
- historical_journal_hub_url = http://192.168.1.239
- historical_journal_capture_logs = true
- historical_journal_capture_all_app_logs = false
- historical_journal_log_app_ids = 4151,4290,3919,4221,3252,3966
- historical_journal_log_retention_hours = 168
- historical_journal_retention_days = 30

**Important:** Explicitly turn capture_all_app_logs OFF; its older
configuration default is true. Confirm IDs on your own hub; IDs are
specific to that installation. Among previous IDs, 3919 is HPM,
4151 is MCP Rule Server, 4290 Monitor, 4221 Hub Inspector,
3252 Watchtower, and 3966 is the still-unidentified reboot caller.

Save options and restart **the HomeBrain add-on only**.
Do not restart or reconfigure Hubitat.

## Using the dashboard

Open the HomeBrain dashboard from the Home Assistant sidebar. Find
**Hub Diagnostics — external recorder**, above Historical Journal.

Four cards show (with real source timestamps):
1. Free OS memory, obtained externally on each probe.
2. Free Java MB, from Hubitat's native ~5-minute sample.
3. Used percent of currently allocated Java heap.
4. HTTP probe response time.

Expand **View memory history & connection incidents** to show:
- Free OS memory, Java memory, allocated heap %, native 5-minute load,
  or response latency.
- Date windows of 1, 6, 24 hours.
- Persisted connectivity loss and recovery episodes.

HomeBrain's UI reads SQLite rather than making hub requests:
- /api/hub-diagnostics/status
- /api/hub-diagnostics/history?hours=6

The database is stored under /data/homebrain-hub-diagnostics.sqlite3,
including its SQLite WAL files, and pruned daily.

## Evidence limits and performance

The recorder requests /hub/advanced/freeOSMemory every 30 seconds,
using a 3-second timeout, and /hub/advanced/freeOSMemoryLast no
more frequently than every 300 seconds. No retries, no extra hub apps,
no event subscriptions or adaptive high-frequency polling. Native Java
and load samples remain five-minute source readings even when displayed
beside more frequent OS observations. CPU load is not CPU utilisation.

Two consecutive failed probes create a connectivity incident; that
does NOT confirm a Hubitat reboot. Compare with Hub Events for
systemStart, lowMemory, severeLoad, update, manualReboot, and HPM logs.
A missing Java sample does not imply that Free Java was zero.
No direct JVM Metaspace metric is exposed.

When reviewing a freeze, compare last successful OS sample, response
latency, first failure, most recent native Java reading, app logs,
and startup or low-memory events. Do not conclude root cause from
correlation alone. HTTP timeouts and local SQLite evidence survive
Hubitat failures; the recorder itself does not survive a simultaneous
Home Assistant failure. Historical backfill is not available.

## Disable or roll back

Turn external_hub_diagnostics_enabled OFF and restart the HomeBrain
add-on. The external SQLite database remains until explicitly removed.
If necessary, roll back to the prior HomeBrain add-on release; no
Hubitat state or existing Monitor/Energy Ledger history is altered.
