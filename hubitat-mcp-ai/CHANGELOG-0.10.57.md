# Hubitat MCP AI 0.10.57

Adds a guarded deterministic Hubitat app controller.

- Lists all, enabled, or disabled apps from `hub_list_apps`.
- Resolves app names safely and supports explicit App IDs.
- Requires clickable Confirm/Cancel before enable or disable writes.
- Uses `hub_set_app_disabled` with the exact App ID.
- Verifies the requested state from the write response and a fresh inventory read-back.
