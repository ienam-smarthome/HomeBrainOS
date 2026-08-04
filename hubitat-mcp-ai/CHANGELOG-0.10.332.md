# Hubitat MCP AI 0.10.332

- makes room-level current-attribute reads capability-aware before choosing a device;
- prevents close-name non-capable devices such as MQTT sockets from outranking actual temperature sources;
- adds deterministic `select`, `use`, `choose`, and `I mean` device-selection commands;
- stores selected device identity only and refreshes authoritative current state for each follow-up;
- keeps multiple valid room sources unresolved with explicit choices;
- adds regression coverage for room-name collisions, explicit selection, and capability filtering.
