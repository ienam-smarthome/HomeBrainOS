# 0.9.4

- Prevent stale device entities from leaking into unrelated standalone questions.
- Retain conversation history only for genuine contextual follow-ups.
- Route broad device-inventory requests to `hub_list_devices` instead of `hub_read_devices`.
- Keep named or described device lookup on `homebrain_search_devices`.
- Preserve authoritative structured MCP results during synthesis.
