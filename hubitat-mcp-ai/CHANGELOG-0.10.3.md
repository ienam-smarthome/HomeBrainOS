# 0.10.3

- Widens the read-only Evidence Planner's verb whitelist to include lookup phrasing
  such as `find`, `locate`, `where`, `show`, `check`, `look up` and `look for`, so
  device-lookup questions (e.g. "Find front door") are correctly routed instead of
  falling through to the unified agent with no authoritative home data.
- Syncs the unified agent's tool-selection and live-data-requirement keyword lists
  with the extended home-domain vocabulary (dehumidifier, camera, appliance, room
  names, energy/cost terms), so those queries are offered the correct device-lookup
  tools instead of only discovery tools.
- Replaces the unified agent's error message, which previously always asserted a
  specific ("not redirected to the read-only evidence planner") cause regardless of
  what actually failed, with the real underlying exception text.
- Adds a coverage check to the device-health scan: if the MCP tool response reports
  a total device/inventory count larger than the number of rows actually returned,
  the scan is now reported as incomplete instead of silently under-counting offline
  or stale devices.
