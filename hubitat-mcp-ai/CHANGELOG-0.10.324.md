# Hubitat MCP AI 0.10.324

## Changed

- Contact-history answers now format ISO timestamps as natural local date and time text, for example `11:32 pm on Monday 3 August 2026`.
- Causation-safe contact answers use correct `a`/`an` grammar.

## Safety

- The original authoritative event timestamp remains the source of the answer; formatting does not infer a different timezone or event.
- Unparseable timestamps are preserved rather than guessed.
