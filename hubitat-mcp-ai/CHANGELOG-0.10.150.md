# Hubitat MCP AI 0.10.150

## Changed

- Consolidated prayer times, device-type inventory, compatibility fields, live
  capabilities, unified device indexing, engagement, multi-device control and
  light-usage reads in `fast_fallback_light_usage.py`.
- Preserved named internal stage classes and the exact runtime method-resolution
  order for focused regression coverage.
- Kept device-index summary/detail field constants and label handling in
  explicit index-specific namespaces to prevent collisions with device-type
  presentation fields.
- Redirected tests and repository validation to the consolidated module.

## Removed

- Removed seven superseded sibling modules:
  `fast_fallback_prayer_times.py`, `fast_fallback_device_types.py`,
  `fast_fallback_device_types_compat.py`,
  `fast_fallback_device_types_live.py`, `fast_fallback_device_index.py`,
  `fast_fallback_engagement.py` and `fast_fallback_multi_control.py`.

## Validation

- AST equivalence checks for all eight router class bodies.
- Focused behavior comparison against v0.10.149.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
