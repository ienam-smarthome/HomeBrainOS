# HomeBrain v0.17.79 — Persistent historical evidence replay and command preservation

## Architecture and original motivation

The v0.17.78 causal test correctly retrieved an empty native incident window in 4.3s while retaining the SenseCap D1 Settings `on()` command. The earlier ON/OFF events were present in older native receipts but had rotated out of current Hubitat event history. Repeated changes to answer wording cannot recover expired data.

The HomeBrainOS add-on already provides an **opt-in, SQLite-backed** Historical Evidence Journal introduced in v0.17.25. It subscribes read-only to unofficial LAN `/eventsocket` and optional `/logsocket`, has explicit connection-gap and backlog accounting, and keeps a bounded persistent SQLite database in `/data/homebrain-evidence-journal.sqlite3`. It was not consulted during normal exact-incident state completion, and native device history reads were not preserved.

## This release

- The host's causal source-completion path queries a running, opted-in Evidence Journal for the specific target device's exact time window **before** completing the native Hubitat device-state and producer-log reads. A separate typed `focal_archived_state_history` evidence receipt preserves journal observations, current gap count, source timestamp basis and completeness caveats.
- Only a unique archived ON with an original offset-aware **source timestamp** can establish a historical state boundary in the causal evidence graph. A WebSocket frame that supplies collector reception time only is **not** promoted to verified exact physical timing or origin. If none is verified, the existing safe missing-history conclusion still applies.
- The graph deduplicates a native and an archived state record by absolute timestamp even if one is formatted with `+01:00` and the other in UTC. No source listener is promoted into an initiating app.
- Approved, successful read-only native `hub_list_device_events` and local `homebrain_device_history` calls opportunistically feed the journal with timestamped `switch`, `command-on`, `command-off` and `command-setLevel` rows. For command events, the validated producing app ID and label are kept in source metadata; no unrestricted command descriptions are saved. This is not continuous command capture. Identical source-timestamped rows are deduplicated after restart.
- Opt-in logging, LAN-only URL validation, native history boundaries, retention days/maximum rows, queue-drop accounting, explicit read-only semantics, app-log allowlist and dashboard remain unchanged.
- New regression tests use temporary SQLite only to prove journal replay of evicted ON/OFF, restart-safe command provenance, deduplication, and that collector time cannot serve as an exact source timestamp.

## Enable after updating

Under Home Assistant add-on **Configuration**, set:
```yaml
historical_journal_enabled: true
historical_journal_hub_url: "http://192.168.1.239"
historical_journal_retention_days: 30
historical_journal_max_rows: 100000
historical_journal_capture_logs: false
historical_journal_log_app_ids: ""
```
Restart and open the Evidence Journal status panel. Check `enabled`, `started`, `connected.events`, `event_rows`, `last_received.events`, dropped counts and gaps. The database is stored in the add-on's persistent `/data` and survives normal upgrades. Avoid enabling app logs unless needed and you have explicitly selected safe app IDs.

**No historical backfill** can recover the already-rotated 14 October event. Newly captured ON/OFF state events and opportunistic native command receipts can support later investigations. This version does not modify devices or Hubitat rules and does not claim continuous event completeness.
