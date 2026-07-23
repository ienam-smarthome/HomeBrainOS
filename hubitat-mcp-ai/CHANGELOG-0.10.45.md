# Hubitat MCP AI 0.10.45

## Truthful CI and lower Hubitat load

- Blocking workflows now preserve pytest's failure status when piping output through `tee`.
- A shared test dependency file installs `pytest-asyncio` consistently.
- The maintained release gate is centralized and blocking; historical test debt remains visible in a named non-blocking audit.
- Static MCP catalogue and device metadata caches are retained longer to reduce expensive Hubitat-side catalogue work.
- Live device and dashboard cache defaults are increased conservatively. Controls, verification, writes, and explicit refreshes remain fresh.
- Equivalent device inventory field projections now share a cache entry regardless of field ordering; filtered inventories remain separate.
- Room-first plural requests such as `Find hallway devices` and `Show hallway devices` now return every selected device assigned to that exact Hubitat room.
