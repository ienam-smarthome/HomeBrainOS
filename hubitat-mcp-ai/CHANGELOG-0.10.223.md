# Hubitat MCP AI 0.10.223

## Model-directed device filtering

- Adds `homebrain_filter_devices`, a local read-only function tool for deterministic
  comparisons across arbitrary live Hubitat device attributes.
- Supports equality, inequality, numeric thresholds, containment, and attribute
  existence checks.
- Returns only matches plus total scanned, comparison errors, and completeness.
- Keeps the device manifest identity-only and lets the model decide when filtering
  is required through normal native tool calling.
- Records both the authoritative Hubitat source read and deterministic filter result
  as evidence.
