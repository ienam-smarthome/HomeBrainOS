# Hubitat MCP AI 0.16.112

## Practical complete-window history context

- Replaces routine `unverified event stream` boilerplate on complete semantic-window duration answers with concise practical context.
- Adds deterministic latest in-window state-event evidence so the fallback can state the latest recorded state and last recorded transition safely.
- For a complete `this afternoon` window, the fallback can say that the window was counted from 12:00 and identify the latest recorded switch-off time.
- Reserves `currently on/off` wording for separate current-turn live-state evidence; history-only fallback says `latest recorded state`.
- Keeps the stronger retained-history warning when the event page does not reach the requested window start.
- Adds regression coverage for the exact 0.16.111 Bathroom Light 1 routine Note and for complete-window deterministic repair.
- The routine-note replacement is deterministic, so the practical context is enforced even if the model still emits the old boilerplate.
