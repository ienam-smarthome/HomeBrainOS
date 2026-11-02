# Hubitat MCP AI v0.18.349 — request-local source read reuse

## Observation and generalizable change

The previous read-only fan investigation (v0.18.347, 66.506s, 11 Gemma rounds/19 tools) retrieved a 48-hour, 20-event unfiltered native location-event page and then the local `homebrain_location_events(hours_back=48)` wrapper projecting that same bounded source again. The duplicate did not resolve the scheduler trigger and repeated unrelated location variable updates.

This release begins a generic single source-obligation consolidation, **without another device-specific routing table**.

- After a successful, nonmutating, current-turn `hub_read_devices.hub_list_device_events` with NO device/attribute/filter/cursor scope and a known window and limit, a subsequent unfiltered `homebrain_location_events` projection can be skipped **only** if its requested window and event limit are no larger than the successful native page.
- Existing native page remains in the model's context; skip response explicitly says it does **not** prove historical completeness. No speculative absence claim, model-authored answer substitution or extra model round.
- Preserve first reads, successful source errors/missing pages, native device-ID-scoped histories, mode/attribute/location-specific filters, greater time windows or event limits, and unrelated tools. Source admission is request-local and limited to read-only investigations; control permissions unchanged.
- Privacy-safe counter `source_projection_reads_reused`; regression tests exercise positive reused source and missing/failed/mutating/filtered/window-larger negatives.

## Limits, measurements and next phase

This safely removes a duplicate data-source path, but **does not prove latency improvement**, model accuracy or broad planner consolidation. The v0.18.348 Dehumidifier 1 read-only cycle test was supplied to the user; no returned trace yet, so do not report a result. The broader target is unifying provider rounds and overlapping retries with source-attested completion while preserving Claude-style naturalness. Source coverage and exact fact truth remain independent obligations.

No Hubitat/Home Assistant devices, rules, storage, backups or settings changed. Merge only if all exact-head Python, container and CI checks green.
