# Hubitat MCP AI 0.10.250

- Adds a deterministic automation-status service for apps and Rule Machine rules.
- Normalises every returned item into active, disabled, paused, broken, or unknown state using explicit precedence.
- Exposes structured `automation_items` in `/api/ask` responses.
- Routes read-only automation status requests without relying on model formatting or requiring Ollama availability.
- Preserves authoritative evidence receipts for both app and rule reads.
