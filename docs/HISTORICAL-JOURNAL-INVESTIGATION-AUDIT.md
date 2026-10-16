# Historical Journal — operational and investigation audit

This audit distinguishes **implemented repository behavior** from **live runtime state**. A GitHub source inspection cannot establish the add-on's current socket connectivity or event counts.

## Confirmed source-level implementation (main at 0.17.80)
- `historical_evidence_journal.py`: opt-in live Hubitat `/eventsocket` and optional app-ID-allowlisted `/logsocket` capture into persistent SQLite, with bounded ingestion, retention, queue-drop and connection-gap tracking.
- Since 0.17.79, verified native MCP `hub_list_device_events` data can be opportunistically written through as eligible state/command events, preserving source time and app producer identifiers when available. These records **do not establish comprehensive command capture**.
- `causal_evidence_planner.py`, `causal_timeline.py`, `mcp_agent_orchestrator.py` and focused motion-lockout modules contain journal-aware retrieval/reconciliation paths. This establishes that the archive is referenced by production code, **not** that every incident invokes it or that its hypotheses are optimal.
- `status()` reports `enabled`, `started`, per-stream `connected`, `last_received`, rows, event/app-log counts, `captured_app_log_counts`, gaps/open gaps, dropped rows and errors. `coverage_complete` is deliberately always false.
- `query()` requires exact device/app ID plus timezone-aware interval; it returns at most 200 rows and always marks historical coverage incomplete. `recent_events()` shows only device event samples, never raw private app-log messages.

## Live validation (must be run on the actual add-on; read-only)
1. Confirm running add-on version and options `historical_journal_enabled`, Hubitat LAN URL, retention and row cap. **Do not share secrets**.
2. Inspect in-app **Historical Journal** and `GET /api/evidence-journal/status`: `started`, `connected.events`, `connected.logs` where enabled, `error`, `rows`, `event_rows`, `app_log_rows`, `dropped_this_run`, `open_gaps`, `last_persisted_device_event`, timestamps, total gaps and tracked IDs.
3. Refresh twice after naturally occurring device events. Verify `event_rows` or the latest received event advances; connected sockets alone are not proof of ingestion. Restart add-on and confirm persisted rows survive; do not intentionally actuate devices during a diagnostic.
4. Use an exact device ID and bounded known incident time in `GET /api/evidence-journal/events`. Compare `source_time`, `observed_at`, `received_at`, `timestamp_basis`, `source`, `attribute`, `value`, and gaps against a corresponding native MCP history read. Never treat reception time as a physical event time.
5. For app decisions, confirm `historical_journal_capture_logs=true`, the app ID is in the allowlist and `captured_app_log_counts[app_id]` advances during ordinary activity. Empty logs do not prove that an app did not run.
6. Ask a read-only causal question. Review **Copy technical** evidence receipts to confirm the journal was *queried for the correct incident-window and device/app*, its observations were used in the final answer, and conflicting native/source facts were retained.

## Investigation quality gates
- Reconstruct the focal OFF/ON sequence, not only the final ON.
- Rank actual app command provenance ahead of ungrounded generic external-controller narratives; acknowledge OFF/report delay counterevidence.
- Never infer uninterrupted capture from count, connectivity or `coverage_complete=false`.
- Check exact journal/native source time, producer ID, replay/read-through duplicates, capture gaps and truncation before evaluating relative timing.
- Select a discriminating follow-up (e.g., MQTT origin vs Hue Bridge action) only if the source is accessible; otherwise identify the missing external record.
- Redact credentials at acquisition/prompt and in technical receipts, and test exposure explicitly.
- Avoid duplicate journal/native observations being counted as independent corroboration.

## Potential issue to verify with integration tests
The journal's `query()` orders by `observed_at` and returns a bounded first page but does not attach a separate `truncated` boolean when the limit is reached. Callers must therefore treat a full response as *potentially capped*, not a complete incident stream. This is a **coverage signaling risk**, not proof of missing data in the live database.

## Acceptance
Code review + CI + actual HA runtime status + live read-only test evidence are all required before claiming Historical Journal fully functional and used correctly. This document alone makes no changes to running collection.
