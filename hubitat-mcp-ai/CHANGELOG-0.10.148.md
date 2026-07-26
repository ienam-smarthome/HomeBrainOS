# Hubitat MCP AI 0.10.148

## Changed

- Consolidated verified controls, authoritative attention, group controls,
  device health and speech-aware matching in
  `fast_fallback_device_health.py`.
- Preserved separate device-health and speech-aware class entrypoints within
  the consolidated module.
- Redirected production consumers, regression coverage and repository
  validation to the consolidated owner.

## Removed

- Removed the superseded `fast_fallback_verified.py`,
  `fast_fallback_attention.py`, `fast_fallback_groups.py` and
  `fast_fallback_speech.py` sibling layers.

## Validation

- AST equivalence check for all five moved class bodies.
- Health/attention focused regression comparison against v0.10.147.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
