# Hubitat MCP AI 0.10.190

## Log-domain routing overlap fix

- Narrows the bounded request-diagnostics matcher to explicit HomeBrain,
  assistant, or request-log wording.
- Stops bare `Check logs for any issues` requests from shadowing semantic
  household-health interpretation.
- Adds regression coverage for both the explicit self-diagnostics route and
  the ambiguous household-health fall-through.
