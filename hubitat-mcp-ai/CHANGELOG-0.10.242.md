# Hubitat MCP AI 0.10.242

## Deterministic service boundaries

- Extracts device target resolution, control execution, and state verification
  from the agent orchestrator into `device_control_service.py`.
- Extracts exhaustive attribute filtering and active light, room, and switch
  queries into `device_query_service.py`.
- Keeps the orchestrator focused on native tool dispatch, evidence handling,
  confirmations, and conversation flow.
- Preserves the native function-calling architecture: the model selects
  high-level tools while deterministic Python services perform correctness-
  sensitive resolution, filtering, counting, execution, and verification.
- Retains compatibility shims for existing callers and tests without adding
  phrase-specific routing or legacy word patches.
