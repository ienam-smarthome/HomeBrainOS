# 0.10.140

## HomeBrainOS 2.0 execution contracts

- Introduces typed `ExecutionRequest` and `ExecutionResult` contracts.
- Defines the three authoritative execution lanes: `fast-control`, `fast-read` and `agent`.
- Defines explicit verification states: not attempted, accepted, verified, failed and not applicable.
- Adds a compatibility bridge that annotates existing responses without removing legacy route names.
- Exposes `execution_lane` and `verification_state` for diagnostics and future routing consolidation.
- Adds regression coverage for verified controls, unsupported writes and legacy route mapping.
