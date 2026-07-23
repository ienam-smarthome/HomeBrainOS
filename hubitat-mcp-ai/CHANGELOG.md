# Hubitat MCP AI changelog

## 0.10.57

- Adds deterministic Hubitat app inventory, including enabled, disabled, and unknown states.
- Adds guarded app enable/disable control through `hub_set_app_disabled`.
- Requires clickable confirmation before every app write and uses the exact App ID.
- Verifies writes from both the MCP response and a fresh `hub_list_apps` read-back.
- Supports partial-name selection and explicit App ID commands.

## 0.10.56

- Adds a live, deterministic MCP app-management capability diagnostic.
- Reports app inventory, app state read-back, and app enable/disable write support separately.
- Includes a developer-ready suggested MCP contract when support is missing.
- The diagnostic is read-only and never changes an app.

Previous release history is preserved in `CHANGELOG-history-through-0.10.55.md`.
