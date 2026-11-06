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
- external_hub_diagnostics_cpu_cores = 4 (logical cores on the C8 Pro)
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

Five cards show (with actual source timestamps):
1. Free OS memory, obtained externally on each probe.
2. Free Java MB, from Hubitat's native ~5-minute sample.
3. Used percent of currently allocated Java heap.
4. Five-minute CPU load equivalent (%) using the configured logical-core count.
5. HTTP probe response time.

Expand **View memory history & connection incidents** to show:
- Free OS memory, Java memory, allocated heap %, 5-minute load equivalent
  (%) or original 5-minute load average, and response latency.
- Date windows of **1, 6, 24, 72, 168, or 720 hours** (1 hour to 30 days), limited by the recorder's configured retention.
- Persistent connectivity-loss and recovery episodes, independently labelled.
- Confirmed **Hubitat systemStart** events as amber vertical chart markers, with captured firmware build when available. The marker's time is from Hubitat's timezone-aware event record; this does not prove why the hub restarted.

**Unified incident timeline (v0.18.430):** The top expandable section uses
the same selected range as the existing detailed history. It plots real external
free-OS-memory observations and distinct native five-minute CPU load-equivalent
readings on two independent vertical scales, aligned to one timestamp axis.
Red shaded intervals represent failed external probe episodes (not confirmed
reboots); amber dashed lines represent offset-aware Hubitat `systemStart`
records. The event list highlights the actual observed minimum OS memory,
maximum CPU-load equivalent, startup records and incident start/recovery timestamps.
Select **Inspect time** or hover/touch the graph to compare the nearest *saved*
observations with their own original timestamps; unsampled periods remain
unknown, never zero.

Select **Inspect Historical Journal** to open the existing journal's review
section, or **View source records (JSON)** to inspect the locally stored,
bounded timeline payload. Those are context/evidence routes, not an automatic
causal log join. The timeline may include an earlier incident overlapping the
selected range. Initial history may be incomplete and older events are never
synthesized.

HomeBrain's UI reads SQLite rather than making hub requests:
- /api/hub-diagnostics/status
- /api/hub-diagnostics/timeline?hours=168
- /api/hub-diagnostics/history?hours=6&metric=free_os_mb
- /api/hub-diagnostics/history?hours=720&metric=java_free_mb

The 30-day graph **does not fetch tens of thousands of points into the browser**. Only actual first/last, minimum/maximum and gap-boundary observations from bounded time buckets are returned. Minima such as a short low-memory dip are preserved instead of averaged away, and missing intervals remain distinguishable. The original 30-second samples remain available in SQLite until retention expires.

The database is stored under /data/homebrain-hub-diagnostics.sqlite3,
including its SQLite WAL files, and pruned daily.

## Evidence limits and performance

The recorder requests /hub/advanced/freeOSMemory every 30 seconds,
using a 3-second timeout, and /hub/advanced/freeOSMemoryLast no
more frequently than every 300 seconds. It also reads `/hub/eventsJson` at most every 300 seconds to collect genuine systemStart records. A Hubitat event must include an explicit timezone-offset timestamp before being plotted as a reboot/startup. Events unavailable from the hub cannot be reconstructed. No retries, no extra hub apps,
no event subscriptions or adaptive high-frequency polling. Native Java
and load samples remain five-minute source readings even when displayed
beside more frequent OS observations. CPU load equivalent is calculated
as 5-minute load average / configured logical processor count × 100.
For the C8 Pro with 4 logical cores, 0.76 load = 19.0% load equivalent.
It is **not** measured processor utilisation and may exceed 100% if
the system has more runnable tasks than processors. Adjust the configured
core count if monitoring a different hub. The derived percentage uses
existing native samples, makes no extra hub requests and is not written
back into the retained raw samples.

Two consecutive failed probes create a connectivity incident; that
does NOT confirm a Hubitat reboot. A recorded `systemStart` event confirms a startup, not its cause; a missing event does not prove that no restart occurred. Compare with Hub Events for
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
