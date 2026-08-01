# Hubitat MCP AI 0.10.289

## Changed

- Routes the production FastAPI runtime through `homebrain_agent.UnifiedMCPAgent`.
- Preserves the established unified MCP tool loop while delegating final no-more-tools synthesis to `FinalAnswerCoordinator`.
- Keeps the original public agent API and inherited safety, confirmation, evidence, and cancellation contracts intact.

## Tests

- Verifies the production agent remains a `UnifiedMCPAgent` compatibility subtype.
- Verifies final synthesis uses an empty tool list and the canonical evidence-only instruction.
- Verifies the runtime imports the coordinated production agent rather than the base orchestrator directly.
