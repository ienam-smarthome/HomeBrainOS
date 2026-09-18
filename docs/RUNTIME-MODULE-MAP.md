# Runtime module map

This is the authoritative inventory of shipped Python modules under `hubitat-mcp-ai/rootfs/app/`.

The repository drift test compares this table directly with the live directory. Add, remove, or rename a row in the same pull request as the corresponding runtime module change.

| Module | Role |
| --- | --- |
| `agent_prompt_policy.py` | Builds the system prompt and optional identity manifests. |
| `aggregate_fallback_policy.py` | Keeps generic value/valueStr aggregate fallbacks request-local and suppresses them after complete non-empty canonical meter evidence. |
| `api_response_builder.py` | Builds the stable API response and presented metrics. |
| `app.py` | Owns FastAPI routes, configuration, shared services, and request coordination. |
| `automation_ideas_service.py` | Asks the model for grounded, creative new-automation suggestions (never factual claims). |
| `automation_status_service.py` | Reads and normalises Hubitat automation status. |
| `capability_grounding.py` | Prevents unsupported capability-denial claims. |
| `chat_transport.py` | Owns provider HTTP, streaming, and response assembly. |
| `chatgpt_mcp.py` | Exposes the opt-in ChatGPT-facing Streamable HTTP MCP transport and high-level HomeBrainOS tools. |
| `confirmation_policy.py` | Decides whether structured actions require confirmation. |
| `confirmation_store.py` | Stores, expires, consumes, and cancels pending confirmations. |
| `confirmed_action_coordinator.py` | Revalidates and executes confirmed action groups. |
| `contact_history_queries.py` | Parses and presents bounded contact-history follow-ups and calendar-day aggregations. |
| `contextual_read_fast_path.py` | Parses and presents deterministic session-context attribute reads and motion aggregation. |
| `deterministic_tool_presenter.py` | Formats fixed answers for supported deterministic reads. |
| `device_claim_grounding.py` | Grounds a named-device claim in the final answer against this turn's device-scoped evidence. |
| `device_control_service.py` | Executes bounded device-control operations. |
| `device_history_service.py` | Resolves one device and reads bounded event history. |
| `device_query_service.py` | Performs read-side inventory queries and aggregation. |
| `device_read_contract.py` | Centralizes Hubitat device-list projection modes, state-field normalization, and projected-state shape validation. |
| `device_state_summary.py` | Provides shared pure device-state summary helpers. |
| `device_target_resolver.py` | Resolves natural-language targets to concrete devices. |
| `time_expressions.py` | Shared deterministic clock-time recognition (parsing an isolated "at &lt;time&gt;" token, never scanning free text for meaning); used by `rule_authoring_service.py` and `device_control_service.py`. |
| `direct_outcome_context.py` | Owns request-local evidence, choice, request-class, and mutation context. |
| `evidence_ledger.py` | Builds a compact current-turn checked-source ledger for final synthesis. |
| `evidence_recorder.py` | Stores sanitised request-scoped evidence receipts. |
| `evidence_source_guard.py` | Corrects final claims that contradict successful current-turn source availability. |
| `final_answer_coordinator.py` | Owns the final no-more-tools synthesis round and injects the current-turn evidence ledger. |
| `grounding_policy.py` | Applies deterministic grounding retry and refusal policy. |
| `history_result_enrichment.py` | Enriches bounded model-driven history reads with uniquely inferable binary attributes and safe post-window boundary evidence. |
| `history_cardinality_guard.py` | Corrects exhaustive interval-count claims that contradict deterministic temporal evidence. |
| `history_temporal_analysis.py` | Derives bounded state intervals, deterministic duration totals, and bounded interval proof from authoritative device events. |
| `history_time_windows.py` | Parses request-scoped calendar phrases and resolves explicit local-time history windows. |
| `investigation_policy.py` | Central shared classification for causal and analytical history requests so orchestration and final synthesis use the same request intent. |
| `homebrain_agent.py` | Production UnifiedMCPAgent composition and metrics wrapper. |
| `hub_info_service.py` | Reads refreshed Hub Information Driver state. |
| `hub_timezone.py` | Resolves and briefly caches the authoritative Hubitat IANA timezone for semantic history windows. |
| `live_evidence_authority.py` | Combines live evidence receipts with grounding decisions. |
| `location_correlation.py` | Computes deterministic tight temporal proximity between observed device-history interval boundaries and current-turn location/mode events. |
| `location_correlation_guard.py` | Corrects categorical final no-correlation claims when current-turn location evidence contains a tightly adjacent subject transition, while preserving correlation-versus-causation. |
| `location_event_queries.py` | Parses and presents bounded hub location-event (mode change) follow-ups. |
| `location_privacy.py` | Redacts precise-location device attributes (GPS, address, map tiles, journey logs) from provider-bound tool results. |
| `mcp_agent_orchestrator.py` | Coordinates the native tool-calling agent loop. |
| `mcp_client.py` | Implements Hubitat MCP JSON-RPC transport and tool access. |
| `mcp_retry_metrics.py` | Records actual retry attempts begun at the MCP transport boundary. |
| `model_context_policy.py` | Bounds copied provider conversation and tool-result context. |
| `natural_datetime.py` | Formats authoritative ISO event timestamps for natural-language answers. |
| `observed_agent_outcome.py` | Builds the immutable production outcome with request metrics. |
| `provider_token_estimator.py` | Estimates provider token usage conservatively. |
| `reasoning_policy.py` | Tracks native tool-round shape, selected-device clarification constraints, and generic evidence-review/synthesis contracts without question-specific routing. |
| `request_classification.py` | Provides non-authoritative presentation and manifest hints. |
| `request_metrics.py` | Collects fixed privacy-safe counters and timings. |
| `request_observation.py` | Owns request metrics lifecycle, cancellation/failure classification, and observed-outcome construction. |
| `request_outcome_policy.py` | Classifies completed requests from fixed privacy-safe counters with explicit precedence. |
| `rule_authoring_service.py` | Compiles supported daily schedules into guarded rule writes. |
| `rule_proposal_confirmation.py` | Resolves a handled rule-authoring proposal into a response message, running proposed writes through the confirmation policy and queuing them. |
| `technical_metrics_presenter.py` | Converts fixed metrics and outcomes into UI-safe rows. |
| `synthesis_context.py` | Preserves bounded privacy-redacted current-turn tool-result excerpts for the final no-tools reasoning synthesis pass. |
| `synthesis_validator.py` | Detects deterministic factual conflicts in model synthesis and supplies a localized repair baseline without replacing supported analysis. |
| `token_aware_context_policy.py` | Applies stricter model-aware context ceilings. |
| `tool_discovery_catalog.py` | Owns prompt-independent tool visibility and expansion. |
| `tool_catalog_assembly.py` | Combines a request's already-fetched remote tools with the fixed local tool set into a ready `ToolDiscoveryCatalog`. |
| `tool_executor.py` | Dispatches approved calls and records normalised results. |
| `tool_registry.py` | Defines local schemas and structured tool effects. |
| `webui.py` | Renders the Home Assistant ingress interface. |
