# Hubitat MCP AI 0.10.144

## Changed

- Routed deterministic Hubitat app enable/disable verification through the
  central `StateVerification` service.
- Preserved existing response messages, intent names and technical compatibility
  fields.
- Kept write-response verification ahead of independent app-inventory
  readback.

## Validation

- App controller, verification service and execution-contract tests.
- Repository layout validation.
- Blocking release gate.
