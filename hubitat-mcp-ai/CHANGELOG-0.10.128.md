# Hubitat MCP AI 0.10.128

## Changed

- Split terminal entity reads into focused handlers for power accounting,
  full device inventory, explicit device lookup and device attribute reads.
- Retained one shared deterministic entity-resolution path for ambiguity,
  room matching and confidence checks.
- Preserved existing MCP calls, response structures and user-visible wording.

## Validation

- Python compilation passed.
- Repository layout validation passed locally.
- 56 focused deterministic entity-read and power-accounting tests passed.
- Git diff validation passed.
- Cluster analysis rerun.
