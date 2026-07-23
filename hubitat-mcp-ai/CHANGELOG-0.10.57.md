# 0.10.57

Adds guarded deterministic Hubitat app management.

- Lists all, enabled, or disabled apps from `hub_list_apps`.
- Resolves exact names and App IDs.
- Presents clickable selection for partial matches.
- Requires Confirm or Cancel before `hub_set_app_disabled` is called.
- Verifies the requested disabled state from the write response and app inventory read-back.
