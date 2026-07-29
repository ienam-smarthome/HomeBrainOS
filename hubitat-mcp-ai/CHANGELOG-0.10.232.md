# Hubitat MCP AI 0.10.232

## Speech-safe device target resolution

- Adds a deterministic, confidence-gated device target resolver for high-level
  light and switch control.
- Normalizes spacing, punctuation, parenthesized state decorations, and spoken
  number words such as “two” versus `2`.
- Evaluates Hubitat `label`, `name`, `displayName`, and `deviceLabel` fields.
- Accepts a unique type-constrained `labelFilter` result only when it clears a
  safe similarity threshold.
- Ranks multiple candidates and auto-selects only when the best score is both
  high-confidence and clearly ahead of the runner-up.
- Penalizes conflicting device numbers so “Light 2” cannot silently select
  “Light 1”.
- Fails closed with the closest candidate names when a request remains
  ambiguous.
- Keeps resolution deterministic and independent of LLM-generated entity
  rewriting.

