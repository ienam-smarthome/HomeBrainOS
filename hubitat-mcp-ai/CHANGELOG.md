# Hubitat MCP AI changelog

## 0.10.57

- Adds deterministic Hubitat app inventory with enabled, disabled, and unknown states.
- Adds guarded app enable/disable commands through `hub_set_app_disabled`.
- Requires clickable Confirm/Cancel before every app write.
- Verifies writes from the MCP response and independent `hub_list_apps` read-back where available.
- Supports exact App IDs and clickable selection for partial-name matches.

## 0.10.56

- Adds a live, deterministic MCP app-management capability diagnostic.
- Reports app inventory, app state read-back, and app enable/disable write support separately.
- Includes a developer-ready suggested MCP contract when support is missing.
- The diagnostic is read-only and never changes an app.

Previous release history is preserved in `CHANGELOG-history-through-0.10.55.md`.
