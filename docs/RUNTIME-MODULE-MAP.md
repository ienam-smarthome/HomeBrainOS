# Runtime module map

This is the authoritative inventory of shipped Python modules under `hubitat-mcp-ai/rootfs/app/`.

The repository drift test compares this table directly with the live directory. Add, remove, or rename a row in the same pull request as the corresponding runtime module change.

| Module | Role |
| --- | --- |
| `agent_prompt_policy.py` | Builds the system prompt and optional identity manifests. |
| `api_response_builder.py` | Builds the stable API response and presented metrics. |
| `app.py` | Owns FastAPI routes, configuration, shared services, and request coordination. |
| `automation_status_service.py` | Reads and normalises Hubitat automation status. |
| `capability_grounding.py` | Prevents unsupported capability-denial claims. |
| `chat_transport.py` | Owns provider HTTP, streaming, and response assembly. |
| `confirmation_policy.py` | Decides whether structured actions require confirmation. |
| `confirmation_store.py` | Stores, expires, consumes, and cancels pending confirmations. |
| `confirmed_action_coordinator.py` | Revalidates and executes confirmed action groups. |
| `contact_history_queries.py` | Parses and presents bounded contact-history follow-ups and calendar-day aggregations. |
| `deterministic_tool_presenter.py` | Formats fixed answers for supported deterministic reads. |
| `device_control_service.py` | Executes bounded device-control operations. |
| `device_history_service.py` | Resolves one device and reads bounded event history. |
| `device_query_service.py` | Performs read-side inventory queries and aggregation. |
| `device_state_summary.py` | Provides shared pure device-state summary helpers. |
| `device_target_resolver.py` | Resolves natural-language targets to concrete devices. |
| `direct_outcome_context.py` | Owns request-local evidence, choice, request-class, and mutation context for deterministic outcomes. |
| `evidence_recorder.py` | Stores sanitised request-scoped evidence receipts. |
| `final_answer_coordinator.py` | Owns the final no-more-tools synthesis round. |
| `grounding_policy.py` | Applies deterministic grounding retry and refusal policy. |
| `homebrain_agent.py` | Production UnifiedMCPAgent composition and metrics wrapper. |
| `hub_info_service.py` | Reads refreshed Hub Information Driver state. |
| `live_evidence_authority.py` | Combines live evidence receipts with grounding decisions. |
| `mcp_agent_orchestrator.py` | Coordinates the native tool-calling agent loop. |
| `mcp_client.py` | Implements Hubitat MCP JSON-RPC transport and tool access. |
| `mcp_retry_metrics.py` | Records actual retry attempts begun at the MCP transport boundary. |
| `model_context_policy.py` | Bounds copied provider conversation and tool-result context. |
| `natural_datetime.py` | Formats authoritative ISO event timestamps for natural-language answers. |
| `observed_agent_outcome.py` | Builds the immutable production outcome with request metrics. |
| `provider_token_estimator.py` | Estimates provider token usage conservatively. |
| `request_classification.py` | Provides non-authoritative presentation and manifest hints. |
| `request_metrics.py` | Collects fixed privacy-safe counters and timings. |
| `request_observation.py` | Owns request metrics lifecycle, cancellation/failure classification, and observed-outcome construction. |
| `request_outcome_policy.py` | Classifies completed requests from fixed privacy-safe counters with explicit precedence. |
| `rule_authoring_service.py` | Compiles supported daily schedules into guarded rule writes. |
| `technical_metrics_presenter.py` | Converts fixed metrics and outcomes into UI-safe rows. |
| `token_aware_context_policy.py` | Applies stricter model-aware context ceilings. |
| `tool_discovery_catalog.py` | Owns prompt-independent tool visibility and expansion. |
| `tool_executor.py` | Dispatches approved calls and records normalised results. |
| `tool_registry.py` | Defines local schemas and structured tool effects. |
| `webui.py` | Renders the Home Assistant ingress interface. |
