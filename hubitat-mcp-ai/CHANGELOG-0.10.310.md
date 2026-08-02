# Hubitat MCP AI 0.10.310

## Changed

- Classifies a normally returned ambiguous device resolution as `unresolved` instead of `success`.
- Keeps grounding refusal precedence as `refused`.
- Presents the fixed `unresolved` outcome in privacy-safe technical metrics.
- Allows live soak validation to recognise the new fixed outcome.

## Safety

- Outcome classification uses only the deterministic resolver-boundary counter.
- It does not inspect prompts, model wording, device names, session identifiers, or tool arguments.
