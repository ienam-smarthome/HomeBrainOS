# 0.16.158

- Fix `DeviceQueryService` room health reconciliation referring to nonexistent `_mcp` rather than initialized `mcp` client.
- Restore the room-filter path so explicit device health can be reconciled without an AttributeError.
- Retain offline-sensor occupancy and environmental freshness rules introduced in 0.16.157.

Pending CI and live acceptance validation. No device-control changes.
