# Hubitat MCP AI 0.10.27

## Entity and execution core foundation

- Adds a typed central device-resolution contract with explicit resolved, grouped, ambiguous, not-found, and unsupported-action outcomes.
- Adds deterministic scoring for exact labels, normalised labels, room assignments, device type, ordinals, fuzzy similarity, and requested capabilities.
- Adds diagnostic match reasons so device-selection failures are easier to trace.
- Adds regression coverage for Fan Switch versus Fan Boost, numbered living-room lights, FP2 lux sensors, front-door contacts, ambiguity, and group control.
- Adds a staged migration plan for routing, planner recovery, execution evidence, verification states, and structured conversation context.

This release is additive: existing control and planner routes remain unchanged while the shared resolver foundation is introduced for gradual integration.
