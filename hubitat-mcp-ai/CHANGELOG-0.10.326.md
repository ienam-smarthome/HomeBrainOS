# Hubitat MCP AI 0.10.326

## Fixed

- Resolve pronoun-only contact-history follow-ups such as `When did it open before that?` from the browser session's saved authoritative history reference before generic device resolution.
- Support deterministic `after that` contact-history follow-ups as well as `before that`.
- Keep count and filtered-list history requests from replacing the last single-event reference.
- Deduplicate and clean repeated generic clarification candidates before presenting choices.
- Return an unresolved outcome when a relative-history question has no session reference instead of inventing a target.

## Unchanged

- Device control, sensitive confirmation, grounding, transport cancellation, and Rule Machine behaviour are unchanged.
