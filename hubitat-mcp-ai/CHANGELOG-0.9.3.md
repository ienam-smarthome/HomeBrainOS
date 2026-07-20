# 0.9.3

- Validate targeted device-search field projections against the live `hub_list_devices` MCP schema.
- Remove unsupported `type` and `deviceType` projections.
- Retry inventory reads without an optional field projection when MCP server versions reject it.
- Add regression coverage for the current Hubitat MCP field contract.
