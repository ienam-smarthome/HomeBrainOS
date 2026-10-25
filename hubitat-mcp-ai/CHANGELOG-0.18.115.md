# HomeBrainOS 0.18.115 — Enforce room scope in live light/switch answers

## Live problem
The user asked: "which livingroom lights are currently on?".
HomeBrain v0.18.114 called `homebrain_active_lights` with `{}`
and answered "6 lights are on" with devices from bedrooms and the hallway,
because that tool's schema only supported the whole home and its result was
presented as a final answer without checking the user's requested room.

This is a **scope contract defect**, not a reasoning-quality or historical
evidence problem. Making only the LLM more verbal would not solve it.

## Implementation
- Expand `homebrain_active_lights` and `homebrain_active_switches` with
  optional `room` schema parameters, keeping existing empty arguments
  compatible for real whole-home questions.
- Independently pass the ORIGINAL request question through the existing
  request-scoped agent context into both live aggregation implementations.
- Match candidate scope solely against authoritative live Hubitat room names:
  `livingroom`, `Living Room`, case/punctuation variants match the
  authoritative `Living Room` assignment. No hardcoded room inventory.
- Enforce the verified room constraint *after* determining current switch
  states; never leak devices from other rooms into a scoped answer.
- If a model-selected tool's room argument contradicts a clearly named user
  room, the user's original room wins.
- Unknown supplied room or unsupported exclusion fails closed with no
  whole-home list, rather than silently omitting the requested scope.
- Render concise, scope-specific answers including zero-on cases and counts;
  preserve global whole-home behaviour when no room was requested.
- Regression tests reproduce the exact user question, other rooms, zero
  living-room lights, wrong model room, switches, schema contract and the
  actual agent wrapper with a model-omitted room argument.

No Hubitat devices, rules, scripts, or settings are changed.
