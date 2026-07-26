# Hubitat MCP AI 0.10.147

## Changed

- Consolidated the base, weather and authoritative live-state fast-fallback
  layers into `fast_fallback_live.py`.
- Preserved the effective runtime routes for hub information, rooms, rules,
  weather, attention, live devices, switches, batteries and home status.
- Redirected direct regression coverage and repository validation to the
  consolidated live owner.

## Removed

- Removed the superseded `fast_fallback.py` and
  `fast_fallback_weather.py` inheritance layers.

## Validation

- Fast-fallback family regression comparison against v0.10.146.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
