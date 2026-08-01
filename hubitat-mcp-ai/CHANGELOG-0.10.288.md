# Hubitat MCP AI 0.10.288

## Changed

- Added a dedicated `FinalAnswerCoordinator` component for the final no-more-tools synthesis round.
- Centralised the canonical final-answer instruction and stable empty-response fallback outside the main orchestrator.

## Safety

- Final synthesis always runs with no declared tools, preventing an extra tool call after the agent loop has decided to conclude.
- Provider cancellation continues to propagate without being converted into a misleading fallback response.

## Tests

- Added coverage for message immutability, empty tool declarations, canonical fallback behaviour, and cancellation propagation.
