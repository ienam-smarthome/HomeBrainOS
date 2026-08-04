# Hubitat MCP AI 0.10.331

- Routes explicit named temperature, humidity, battery, and power questions through the deterministic current-state path.
- Reuses the resolved target snapshot for subsequent browser-session attribute follow-ups.
- Keeps ambiguous device requests unresolved with explicit choices.
- Prevents complete single-value current-state answers from being labelled unresolved.
- Adds regression coverage for explicit named attribute parsing and historical-wording exclusions.
