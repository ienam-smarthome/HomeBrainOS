# Hubitat MCP AI 0.10.30

## Room inventory parser correction

- Fixes `Show devices in the living room` extracting only `living`.
- Preserves `living room` as the requested room name before canonical matching.
- Keeps explicit forms such as `Show the Livingroom room devices` working.
- Adds regression coverage for both show/list and which/what room inventory phrasing.
