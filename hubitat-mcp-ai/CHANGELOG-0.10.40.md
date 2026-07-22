# Hubitat MCP AI 0.10.40

## Compact MCP inventory compatibility

The v0.10.39 deterministic reader required inventory rows to include room,
state, capability or disabled metadata. The live Hubitat MCP server can return
valid compact rows containing only a device identifier and label, so those rows
were discarded before entity matching.

This release:

- treats every row with a recognized device ID and label as a device record;
- shares HomeBrain's established device ID and label alias contract;
- carries the resolved alias ID into `hub_read_devices`;
- verifies `Freezer (MQTT)` resolves from a compact inventory row and reports
  its authoritative live power value of 77 W.
