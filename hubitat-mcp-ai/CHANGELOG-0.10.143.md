# Hubitat MCP AI 0.10.143

## Added

- Added one typed `StateVerification` result backed by the canonical
  `VerificationOutcome` enum.
- Centralised nested field extraction and boolean-state coercion.
- Added focused regressions for verified, accepted, conflicting and failed
  command outcomes.

## Verification policy

1. Inspect the write response first.
2. Perform an independent readback when the write response cannot verify state.
3. Preserve distinct verified, accepted, conflicting and failed outcomes.

## Validation

- Repository layout validation.
- Blocking release gate.
