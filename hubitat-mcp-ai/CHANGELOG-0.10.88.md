# Hubitat MCP AI 0.10.88

## Fixed

- Exact device attribute reads remain bound to the resolved Hubitat device ID.
- A requested device is no longer replaced by another candidate merely because the other device exposes the requested attribute.
- Compact, spaced, hyphenated, and underscored device labels now resolve consistently, including `BathroomMeter` and `Bathroom meter`.
- Leading articles such as `the`, `a`, and `an` are removed from attribute target phrases.
- Broad room metric queries retain bounded candidate probing while exact device queries read only the selected device.

## Validation

- Repository layout validation passed.
- Python compile validation passed.
- Blocking release gate passed: 246 tests.
