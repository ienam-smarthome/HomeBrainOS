# HomeBrain v0.17.74 — Host-source execution and incident evidence preservation

## Live investigation defect

The v0.17.73 acceptance trace recorded `skills_focal_producer_logs=1` but **no `skills_focal_state_window`** and no retained state-event rows. Only the app log read ran. The host-owned source completion loop was using `ToolDiscoveryCatalog.declared_tool("hub_read_devices")`. This broad gateway is *available* on the MCP server but intentionally absent from the model's initial tool-declaration list, so the host silently skipped its mandatory event-window read. This was independent of the earlier timezone issue.

## Architectural correction
- Move host-owned focal source reads into reusable `execute_focal_source_plan`; resolve gateways through `catalog.available_tool`, not the model-facing `declared_tool`. Only the host's predetermined read-only device events and app logs operations are permitted here.
- Never silently mark an inaccessible or failed gateway as verified. Emit structured failure receipts and the aggregate `skills_focal_read_failed` metric. Keep independent source reads running when one fails.
- Preserve exact focal event rows through `project_focal_state_result` even when the generic MCP gateway receipt provides a summary. Cap retained events at 20 **before** evidence redaction, explicitly prioritising the requested ON and the most recent preceding OFF; disclose event-row truncation and unknown source completeness.
- The grounded answer now derives incident-window coverage text from success/failure receipt types. Model-facing phrase substitution cannot stand in for source acquisition.
- Add host-execution regressions that use a catalog where `hub_read_devices` is available but deliberately not declared to the model; test both gateway failure and busy history retention.

## Safety and limits
Read-only. No Hubitat settings, device commands, rule changes or add-on restart were issued. A successful bounded window read does not prove that Hubitat's upstream history is complete; the 19:54:57.946 OFF may still be unavailable in its current retained event stream. Legacy causal wording safeguards remain for investigation paths not yet covered by deterministic skill decisions; removing them without equivalent general regression coverage would risk reopening known false attributions.

## Live acceptance
After upgrading and restarting add-on, repeat historical Livingroom Light 1 investigation. Require a `hub_list_device_events` read for device 7805 using `since`/`until` spanning 2026-10-14 19:54:46–19:55:00 BST; `skills_focal_state_window=1`; inspect `skills_focal_state_rows_retained` and `skills_focal_read_failed`. If the returned stream includes the intervening 19:54:57.946 OFF, the answer must retain it. If not, explicitly distinguish an empty queried window from true historical inactivity.
