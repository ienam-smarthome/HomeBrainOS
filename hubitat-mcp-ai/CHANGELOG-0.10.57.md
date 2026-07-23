# 0.10.57

Adds guarded deterministic Hubitat app management.

- Lists all, enabled, or disabled apps from `hub_list_apps`.
- Resolves app names and App IDs without AI.
- Requires clickable confirmation before every enable/disable write.
- Uses `hub_set_app_disabled` and verifies the returned `disabled` state.
- Performs an independent app-inventory read-back when available.
