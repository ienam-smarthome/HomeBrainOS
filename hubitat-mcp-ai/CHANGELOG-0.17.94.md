# 0.17.94 — Targeted automation history routing

- Prevents targeted requests such as `Show me the recent history of the Livingroom lighting automation` from being misclassified as an all-automation status request merely because they contain `show` and `automation`.
- Sends those questions to the unified MCP agent for evidence-based, scoped analysis instead of enumerating 152 app/rule entries.
- Leaves intentional whole-hub inventory questions on their existing deterministic fast route.
- Adds targeted history vs inventory routing regression tests.

This is a routing correction, not proof the agent can reconstruct historical triggers if history is unavailable. No Hubitat writes. Paid model selection remains separately configured and disabled until enabled in Home Assistant add-on options.
