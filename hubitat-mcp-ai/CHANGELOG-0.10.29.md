# Hubitat MCP AI 0.10.29

## Natural room inventory matching

- Fixes `Show devices in the living room` falling through to single-device lookup.
- Treats `Livingroom`, `living room`, and `living-room` as the same exact Hubitat room.
- Treats `Bedroom1` and `bedroom 1` as the same room while preserving authoritative room membership.
- Adds regression coverage for room candidate extraction and canonical room keys.
