# Hubitat MCP AI 0.16.126

## Fixed
- Call Rule Machine listing with `hub_read_rules` and arguments `{"tool":"hub_list_rules","args":{}}`, matching the established rule-authoring MCP contract rather than sending an empty wrapper call.
- Treat returned `success: false` as a failed read and distinguish tool success from substantive rule coverage.
- Label returned structured rules as not independently complete until verified; no data is never proof of zero rules.
- Add regression tests for the call shape, populated responses and failure handling.

## Safety
- Read-only queries only. No changes to Hubitat automations or devices.
