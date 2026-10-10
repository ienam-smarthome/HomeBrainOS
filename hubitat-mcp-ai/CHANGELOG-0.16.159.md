# 0.16.159

- Improve room-health reconciliation for both exact and contains room filters.
- Remove device-name-based MQTT diagnostic heuristic and use reported status attributes to identify candidates for detail enrichment.

**Validation pending:** A compact context with missing health fields still requires explicit source-coverage verification; do not treat the room-health synthesis issue as fully resolved solely on this change.
