# Hubitat MCP AI 0.10.274

- Extracted stateless sensitive-action decisions into a focused
  `ConfirmationPolicy`.
- Centralised confirmation eligibility based on structured `ToolEffect` values,
  without inspecting raw user-prompt wording.
- Preserved the unique-session requirement, 12-action group ceiling, firmware
  restart warning, single-action prompt, and grouped-action wording.
- Centralised fail-closed wording when a queued gateway is no longer advertised
  before confirmation execution.
- Kept TTL expiry, pending-session capacity, isolated snapshots, reply
  consumption, and cancellation in `ConfirmationStore`.
- Kept tool classification in `tool_registry.py` and confirmed execution in the
  orchestrator through `ToolExecutor`.
- Added direct regression coverage for disabled policy, structured effects,
  empty and oversized groups, invalid sessions, firmware, multiple gateways,
  and missing-tool cancellation wording.
