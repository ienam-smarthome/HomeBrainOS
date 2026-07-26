# Hubitat MCP AI 0.10.149

## Changed

- Consolidated rule/device inventory, dashboard comparisons, essential reads,
  room inventory, release corrections, device status and extended reads in
  `fast_fallback_extended_reads.py`.
- Preserved named internal stage classes for focused regression coverage while
  keeping one module owner and one live downstream endpoint.
- Redirected production consumers, tests and repository validation to the
  consolidated module.

## Removed

- Removed six superseded inventory/room sibling modules:
  `fast_fallback_inventory.py`, `fast_fallback_dashboard.py`,
  `fast_fallback_essentials.py`, `fast_fallback_room_inventory.py`,
  `fast_fallback_release.py` and `fast_fallback_device_status.py`.

## Validation

- AST equivalence check for all seven moved class bodies.
- Inventory/room focused regression comparison against v0.10.148.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
