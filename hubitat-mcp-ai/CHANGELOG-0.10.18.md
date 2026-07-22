# 0.10.18

- Requests only Hubitat MCP-supported device fields for Octopus meter reads.
- Falls back to the complete HomeBrain device index before reporting zero displays.
- Handles both `find octopus` and period-specific meter queries deterministically.
