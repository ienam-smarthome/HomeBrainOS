# Hubitat MCP AI 0.10.323

- Treat leading articles such as “the” as presentation-only when resolving exact device labels for contact-history questions.
- Answer “why did ... open/close” with the relevant contact transition and an explicit causation limitation instead of a full mixed event dump.
- Recover structured clarification choices from deterministic unresolved messages so pronoun-only follow-ups remain unresolved and repeat the choices before any provider call.
- Add regression coverage for exact contact history, causal-history wording, and stored clarification choices.
