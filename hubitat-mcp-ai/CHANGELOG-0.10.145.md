# Hubitat MCP AI 0.10.145

## Changed

- Clarified that gateway routing never relaxes MCP masters, backup, or
  confirmation requirements.
- Distinguished `hub_shutdown` from `hub_reboot`, including the shutdown
  requirement for a manual physical power cycle.
- Added physical-device exclusion and MCP-managed virtual-device deletion
  guidance.
- Documented the automatic rule loop guard and the advisory-only nature of tool
  annotations.
- Required `hub_get_tool_guide` before writing trigger, condition, or action
  JSON.

## Validation

- Runtime safety-prompt regression tests.
- Repository layout validation.
- Blocking release gate.
