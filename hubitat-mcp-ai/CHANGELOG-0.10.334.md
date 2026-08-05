# Hubitat MCP AI 0.10.334

- Preserve the original requested attribute when a WebUI clarification choice is tapped.
- Route clarification choices such as `Bedroom 1 Meter` back through the deterministic named-attribute path instead of submitting the bare device label to the model loop.
- Preserve existing deterministic control-choice behaviour.
- Add regression coverage for attribute and control choice prompt construction.
