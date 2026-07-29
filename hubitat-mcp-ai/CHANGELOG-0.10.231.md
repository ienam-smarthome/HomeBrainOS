# Hubitat MCP AI 0.10.231

## Faster verified routine control

- Offers `homebrain_control_devices` for every otherwise-unclassified write
  request, so devices such as TVs do not fall through to tool discovery.
- Removes `hub_search_tools` and the general attribute-filter schema from the
  generic routine-write path.
- Stops injecting the full identity manifest for routine on/off/toggle requests.
- Resolves named targets with a narrow `labelFilter` device lookup; room-wide
  controls perform one authoritative device lookup.
- Integrates switch-state verification into the high-level tool for on/off
  commands.
- Executes multi-device commands and their verification concurrently.
- Returns immediately from deterministic command and verification receipts,
  without another Ollama round.
- Distinguishes a failed command from a command that was sent but could not be
  verified.

