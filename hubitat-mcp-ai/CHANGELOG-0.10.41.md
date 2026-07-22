# Hubitat MCP AI 0.10.41

## Room-aware deterministic measurements

- Matches a requested location against structured `room`, `roomName` and
  `room_name` values, including nested room objects.
- Ranks exact names first, then room/name overlap, device compatibility and
  advertised attribute support.
- Demotes obvious lights, switches, sockets and plugs for environmental sensor
  reads without preventing their power or energy measurements.
- Performs a bounded maximum of three authoritative detail reads when compact
  inventory leaves several candidates unresolved.

## Regression coverage

- Resolves bathroom humidity when the device label does not contain Bathroom.
- Skips a matching bathroom light and a temperature-only sensor before finding
  the humidity-capable environmental sensor.
- Covers named energy and battery reads using Hubitat attribute aliases.
