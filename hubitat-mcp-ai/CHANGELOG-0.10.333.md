# Hubitat MCP AI 0.10.333

- Keep room-level current-attribute questions on the deterministic fast path.
- Parse the room target and requested attribute separately before the model loop.
- Let capability filtering return one authoritative source or unresolved device choices.
- Prevent room temperature and humidity reads from entering provider discovery and multi-round synthesis.
- Add regression coverage for Bedroom 1 room-level temperature and humidity parsing.
