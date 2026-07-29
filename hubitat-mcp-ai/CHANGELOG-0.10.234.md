# Hubitat MCP AI 0.10.234

- Repairs room-wide light and switch control when the live device response
  omits embedded room metadata.
- Falls back to the enriched short-TTL identity manifest for authoritative
  room membership.
- Normalizes room names so speech variants such as `Living Room` and
  `Livingroom` resolve consistently.
- Keeps light and non-light switch targets separated during room commands.
- Adds regression coverage for both normalized room-name forms and
  multi-device execution.
