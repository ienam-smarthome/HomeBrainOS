# 0.10.138

## Actionable unsupported Rule Machine writes

- Shows the rule's current disabled, paused and status values when enable/disable is unsupported.
- Keeps pause and disable as separate states and never substitutes one for the other.
- Adds a context-aware Pause instead or Resume instead action without sending it automatically.
- Includes the required `hub_set_rule_disabled` MCP contract in technical diagnostics for upstream implementation.
- Adds regression coverage for rules that are enabled but paused.
