# Hubitat MCP AI 0.10.95

## Changed

- Room metric reads now prioritise devices already exposing the requested state.
- Devices advertising matching capability or attribute metadata are ranked ahead of unrelated room devices.
- Room queries can probe up to six bounded candidates instead of only three.
- Devices outside the exact requested room are never probed.
- Named-device reads remain restricted to the resolved named device.

## Fixed

- Room metric failures now report the room rather than blaming an arbitrary device.
- Zero compatible candidates now return a room-level unavailable response.
- Unrelated switches, lights and presence devices are excluded when a matching metric device exists.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Focused entity-read suite passed: 57 tests.
- Blocking release gate passed: 270 tests.
