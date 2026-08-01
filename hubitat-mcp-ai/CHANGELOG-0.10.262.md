# Hubitat MCP AI 0.10.262

- Derive write-versus-read reporting from actual requested tool calls instead of raw query text.
- Remove the text-classifier-triggered “no control tool executed” refusal path.
- Preserve sensitive confirmation at tool-call time and tag evidence receipts with `mutates`.
- Preserve mutation classification after a queued sensitive action is explicitly confirmed.
- Add regression coverage for past-tense and interrogative diagnostic wording containing control verbs.
- Document the rule against text-based mutation gates.
- Align the release gate with the new tool-call-driven behaviour.
