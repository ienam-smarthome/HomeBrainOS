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

**Shared Ask and incident source receipts (v0.18.435):** The ordinary
`/api/ask` causal-claim guard now preserves verified bounded and typed
`hub_list_device_events` system-event time/type facts if actually present in
the published receipts, while still withholding the model's unsupported cause.
For successful or failed `hub_get_logs` calls, it reports separate
`hubEvents`, `past`, `apps` and generic-bounded read counts under
`causal_read_source_coverage`. The dedicated incident endpoint adds
`log_query_modes` and bounded typed app-row counts to
`incident_source_coverage`. Summary-only receipts, an app-mode snapshot and
a successful generic request cannot certify historic app-message coverage.
No additional MCP calls, background recording or Hubitat writes are added;
missing original messages remain missing.

**Source-qualified incident next checks (v0.18.434):** An unsafe model
claim is still withheld, but the report does not stop at that warning.
HomeBrain generates deterministic next read-only checks from the typed
restart-trigger status, app-specific log-read attempts, time-bounded generic
log-query receipts, recorder sample coverage and Historical Journal gaps.
The checks do **not** name a responsible application without evidence.

**Historical-log coverage:** The live 5 November investigations encountered
failed `mode=apps` attempts. The 22:25 incident also contained a successful
date-bounded generic `hub_get_logs` receipt. This newer report distinguishes
these outcomes: success of a generic log request is not evidence that any
particular app's historical log messages were retrieved or read. A Journal
count of app-log receipts likewise does not establish message content.
The response includes an `incident_source_coverage` object with explicit
success/attempt counts and flags that model-proposed hypothesis source
checks are independent from independently verified Hub Events.

Unknown underlying cause remains UNVERIFIED. This update improves
reporting and prioritisation, not the completeness of stored historical
evidence, and introduces no additional Hubitat polling or mutations.
**Source-backed restart trigger assessment (v0.18.433):** In the existing
AI incident response, a separate deterministic evidence section now derives
Hubitat restart context only from successful typed `hub_list_device_events`
receipts with grounded timestamps in the requested window. A `lowMemory`
message explicitly saying critically low memory and rebooting followed by
a confirmed `systemStart` supports a **reported low-memory restart trigger**
but not the identity of the process exhausting memory. A firmware `update`
record followed by startup supports an **update-associated startup sequence**
but does not demonstrate that firmware caused the preceding external OS
memory reading. With missing, failed or truncated source access, absent
events never establish absence of a trigger. Attempted failed app-log reads
are shown as evidence gaps.

The deterministic Hub Events summary is displayed even when the AI prose is
withheld for an unsupported causal conclusion. This preserves useful verified
facts without claiming the full root cause is known. The JSON response adds
`restart_trigger_evidence`, `restart_trigger_status` and
`underlying_memory_cause: unverified`. No new Hubitat polling or writes.
**Evidence-bound AI incident investigation (v0.18.432):** Choose **AI investigate**
beside an observed timeline incident, **AI investigate selected time** after
selecting a graph timestamp, or **Investigate with HomeBrain AI** inside the
read-only incident review. The existing Ask answer area receives the response.
No inference starts until explicitly requested. Free/Ollama, Paid and
configured Claude choices behave exactly as existing HomeBrain requests.

Before model inference, the backend reads the bounded recorder and Journal
SQLite snapshots and supplies a request-scoped, source-labelled JSON capsule
to the existing MCP AI agent. The capsule does not include raw app-log
message bodies. The agent may make additional read-only Hubitat MCP requests
for original Hub Events, firmware update records, performance and app logs.
Those MCP calls are separately accounted for in the evidence receipts.
If both local archives are missing, no AI call is made.

The root cause remains UNVERIFIED unless discriminating source evidence
actually establishes it. A memory dip followed by a firmware update and
restart is a temporal association; it cannot prove what consumed the
memory. A Hubitat log explicitly saying critically low memory triggered
a reboot is stronger evidence for the reboot trigger, not the identity
of a memory-consuming app. Source-time limits, missing log windows and
journal collection gaps must be preserved.

Read-only endpoint: POST /api/hub-diagnostics/investigate accepts at as
offset-aware ISO timestamp, window_minutes of 5/15/30/60 and model_tier
free/paid/claude/auto. The ordinary Ask endpoint also blocks definitive
model cause claims when its typed hypothesis comparisons are unresolved.
No write permissions, autonomous scheduling or new polling are introduced.
**Incident drill-down (v0.18.431):** Select **Investigate** beside a
confirmed startup, connectivity failure/recovery, real OS-memory minimum or
derived native CPU-load maximum. Alternatively select a timestamp on the
timeline and press **Investigate selected time**. The view reads ±15 minutes
by default (5, 30 and 60 minutes selectable) from local recorder and existing
Historical Journal SQLite stores only. It shows exact source times and values,
bounded successful/failed probes, the closest recorded probes before/after the
focus, confirmed startups, recorded connectivity outages, and a preview of
retained device events with their source-time/collector-received distinction.

Historical app logs are represented **only by per-app receipt counts and first/last
collector times**, not by message bodies. Known collection gaps and response caps
are explicitly labelled. Choose **Copy evidence summary** for a bounded report
or **Source JSON** for the exact local response. No AI/model calls, new Hubitat
queries, device writes, scheduled tasks or threshold-based cause claims.

If records fall outside retention or are missing, the interface shows unavailable
evidence, not proven absence. The incident sequence from 5 November (22:25
memory minimum, 22:27 connectivity loss, 22:32 recovery, 22:33 startup,
22:37 native CPU load peak) is a good *example* for validation, but temporal
association does not establish that low memory caused a restart.

HomeBrain's UI reads SQLite rather than making hub requests:
- /api/hub-diagnostics/status
- /api/hub-diagnostics/timeline?hours=168
- /api/hub-diagnostics/incident?at=2026-11-05T22%3A33%3A00%2B00%3A00&window_minutes=15
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
