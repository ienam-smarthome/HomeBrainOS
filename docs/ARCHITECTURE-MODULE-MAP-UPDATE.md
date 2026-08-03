# Architecture module-map update

This companion note records the module-map correction identified during the 0.10.314 grounding-factory review. The maintained runtime contains thirty-five Python modules under `hubitat-mcp-ai/rootfs/app/`, not the twenty-six currently stated in `docs/ARCHITECTURE.md`.

The following live modules must be represented in the canonical module table:

| Module | Role |
| --- | --- |
| `homebrain_agent.py` | Production `UnifiedMCPAgent` subclass constructed by `app.py`; installs token-aware context, coordinated final answers, request metrics, and the request-local live-evidence grounding factory. |
| `token_aware_context_policy.py` | Production context-policy subclass that may tighten, but never loosen, inherited character limits using conservative model-family token estimates. |
| `provider_token_estimator.py` | Dependency-free approximate token estimator used by the production context policy. |
| `live_evidence_authority.py` | Request-local grounding authority combining authoritative `EvidenceRecorder` receipts with bounded retry/refusal decisions and fixed metrics. |
| `final_answer_coordinator.py` | Isolates the final no-more-tools synthesis round from the main tool-calling loop. |
| `request_metrics.py` | Collects privacy-safe request counters and timings and derives fixed outcomes without inspecting prompt or response text. |
| `technical_metrics_presenter.py` | Converts allow-listed request metrics into stable WebUI technical-detail rows. |
| `api_response_builder.py` | Builds the stable `/api/ask` response and includes privacy-safe presented metrics. |
| `mcp_retry_metrics.py` | Records actual retry attempts at the MCP transport boundary through the active request metrics context without parsing logs or response text. |

Fold these rows into `docs/ARCHITECTURE.md`, change the stated module count from twenty-six to thirty-five, and retain the architecture coverage test as the source-of-truth check for future additions/removals.
