# Hubitat MCP AI 0.10.315

## Changed

- Adds a `device_resolution_missing` request metric, distinct from `device_resolution_ambiguous`.
- Records missing resolution when no candidate exists or the only candidate is below the accepted similarity threshold.
- Classifies missing-device resolution as `unresolved` instead of `success`.
- Adds a `Missing-device resolutions` row to technical request metrics.

## Safety

- Uses only a fixed metric counter at the deterministic resolver boundary.
- Does not inspect user-facing answer text, prompts, session identifiers, or tool arguments to classify the outcome.
- Keeps genuinely competing candidates on the existing ambiguity path.

## Validation

- Adds focused tests for empty candidates, a dissimilar single candidate, successful resolution, outcome classification, and technical metric presentation.
