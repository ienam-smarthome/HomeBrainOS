# Hubitat MCP AI 0.10.240

- Preserves Hub Info attribute units in authoritative resource snapshots.
- Formats CPU load together with CPU percentage.
- Reports free memory in KB, MB, or GB using the driver-provided unit, with a
  safe fallback when MCP omits event metadata.
- Reports temperature, database size, and uptime using the same units and
  semantics as the Hub Info driver's HTML summary.
- Presents hub resources as a readable structured list.
