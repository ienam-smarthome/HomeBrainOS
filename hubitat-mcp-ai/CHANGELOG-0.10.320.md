# 0.10.320

## Extract observed outcome construction

- Moves `ObservedAgentOutcome` and the complete base-to-observed field copy into `observed_agent_outcome.py`.
- Leaves `homebrain_agent.py` responsible for request metrics lifecycle rather than result-object reconstruction.
- Preserves every existing response field, confirmation flag, choice list, evidence list, and metrics snapshot.
- Adds focused contract tests for populated and default metrics outcomes.
- Updates the authoritative runtime module map.
