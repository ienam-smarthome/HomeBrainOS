# Hubitat MCP AI 0.10.56

## App-management capability diagnostic

- Adds a deterministic, read-only diagnostic for live MCP app-management support.
- Detects direct and gateway-hidden app inventory tools.
- Reports app state read-back and app enable/disable write capability separately.
- Provides a suggested MCP contract when support is missing:
  - `hub_list_apps -> apps[{id,label,name,disabled,status,type}]`
  - `hub_set_app_disabled({appId, disabled}) -> {success, appId, disabled}`
- Never sends an app write while performing the diagnostic.

Ask HomeBrain:

> Check app management capability

or:

> Can you disable Hubitat apps?
