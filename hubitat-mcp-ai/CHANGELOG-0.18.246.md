# v0.18.246 — All-app app-decision journal, separate 48-hour log retention

## Changes

- Keep the original HomeBrain assistant and the existing persistent Historical Journal. No separate V2 test engine or UI returns.
- When **Historical Journal is enabled**, capture app logs for all Hubitat apps (wildcard `*`) from the existing read-only local Hubitat `/logsocket`. The collector never enables or changes Hubitat app logging, cannot recreate historical messages, and does not send commands.
- **Separate retention limits:** app messages are removed after 48 hours (configurable) with their own 100,000-row cap. Device-event history retains its existing 30-day configurable retention and independent event-row cap; high-volume log storage cannot evict device history by database pruning.
- Secrets are scrubbed before SQLite writes with the existing credential/URL/Bearer scrubber plus the journal-specific token/password scrubber. Stored app messages can still contain other private data; local users should protect journal access and configure log levels sensibly.
- The original multi-device investigation now checks archived app decisions for **only** app IDs independently verified as issued-command producers in successful target device histories. It does not query every app or accept guessed app IDs; at most eight app histories, bounded to the requested incident window and 100 entries per app.
- Only app-log counts, decision categories, collection gaps and collector timestamps enter public investigation receipts; raw log text stays on the local journal. A textual declaration does not prove the app initiated a physical switch ON, and an absence of log rows never proves no execution.
- Historical Journal reads support bounded **last two hours**, last N minutes/hours (up to 48 hours) questions, anchored to current UTC. Old source event receipts cannot satisfy a recent window.
- The journal dashboard reports all-app capture, app-log count and configured log retention. Existing journal browser time window and source/collector distinctions remain intact.

## Operational notes

All-app app-log capture is active by default **only when the Historical Journal itself is enabled**. Users can disable `historical_journal_capture_all_app_logs` and use `historical_journal_capture_logs` plus `historical_journal_log_app_ids` for selective capture. Already saved app logs are pruned to the new 48-hour policy on database initialization/pruning. Existing device-event retention remains unchanged. If the hub does not emit an app log message, collection cannot invent it. External automation decision traces from SmartThings, Home Assistant, Hue or Aqara require their own accessible sources.

## Tests

Verify wildcard app IDs, exclusion of device logs in the app stream, sanitization of token/password/Bearer/query secrets, SQLite retention of 49-hour-old app logs versus 5-day-old device history, preservation of an independent row cap, all-app status, existing per-app allowlist, read-only archived decision metadata, no unverified app IDs, and bounded recent two-hour queries. Existing Hubitat/OpenWrt and device-write safety regressions must remain green.

**Release gate:** full Python suite, Hubitat MCP AI tests, HomeBrainOS release assurance, metadata validation and add-on smoke before merge; live installation and Claude/HomeBrain agreement remain unverified until manually tested.
