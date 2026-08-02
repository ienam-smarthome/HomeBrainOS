# Hubitat MCP AI 0.10.298

## Fixed

- Aligned `technical_metrics_presenter` with the real nested `RequestMetrics`
  snapshot shape (`counters`, `timings_ms`, and `outcome`).
- Corrected production metric names for discovery timing, ambiguous resolution,
  confirmation expiry, and refused outcomes.

## Added

- `/api/ask` now returns privacy-safe `metric_rows` alongside the raw metrics
  snapshot.
- Added integrated regression coverage using real production snapshot shapes.

## Safety

- Only the fixed metric vocabulary is rendered.
- Unknown keys, prompts, device names, tool arguments, session IDs, and dynamic
  labels remain excluded.
