# Hubitat MCP AI 0.10.311

## Changed

- Classifies a normally returned request with a recorded mutation verification failure as `failed` instead of `success`.
- Keeps grounding refusals as the highest-precedence completed outcome.
- Keeps deterministic device ambiguity classified as `unresolved`.

## Safety

- Outcome classification uses only fixed request counters recorded at existing decision boundaries.
- It does not inspect prompts, model wording, device names, session identifiers, or tool arguments.

## Validation

- Covers verification-failure classification, precedence against grounding refusal and unresolved outcomes, and normal successful completion.
