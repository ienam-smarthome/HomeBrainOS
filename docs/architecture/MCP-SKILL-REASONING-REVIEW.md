# Review — Claude's Hubitat MCP skill vs HomeBrain reasoning

**Review date:** 12 October 2026

## Review basis

User-provided `SKILL.md`, `safety-guide.md`, `rule-patterns.md`, and the detailed Bathroom Light 1 request/response trace. HomeBrainOS implementation on `main`: orchestrator, prompts, discovery catalog, transport, reasoning budget, executor, semantic planner, deterministic causal evidence and synthesis validator. This is a source review, not a comparative live execution of Claude and HomeBrain with identical prompts.

## What Claude's skill teaches

1. **The MCP server is authoritative:** use `hub_search_tools` for current capability routing and `hub_get_tool_guide` for operation-specific shapes instead of a fixed handwritten tool map. Search relevant sub-operations, not merely broad request wording.
2. **Progressive disclosure:** retrieve inexpensive targeted identities/attributes first, then only relevant device histories, related app/rule settings, event logs and cross-domain evidence. Avoid massive hub queries; paginate/filter when appropriate.
3. **Rule semantics:** read triggers, conditions, required expressions, actions, scheduling and delayed work separately. Native Rule Machine, Visual Rules Builder, classic apps, and legacy custom rules have distinct authoring and investigation surfaces.
4. **Safety:** exact device identity before control, no fuzzy guess, central Read/Write masters plus deny-only overrides, extra confirm+backup for destructive actions, and respect result/verification contracts.
5. **User-facing synthesis:** answer the user's actual question, not an unprioritized transcript of tool responses.

These are instructions in the uploaded skill, not evidence that Claude actually executed all described tools.

## HomeBrain architecture at review time

- `homebrain_agent.py` supplies a semantic planner for controls and a mostly reasoning-first default for ordinary reads, while preserving several deterministic handling paths. Some direct-control paths are appropriately not model-generated.
- `mcp_agent_orchestrator.py` prefetches causal subject evidence. Once source attribution is sufficient it can immediately render a deterministic answer without a model call (`model: null`), preventing a more exploratory question from being satisfied when the producer is only one part of the requested analysis.
- `tool_discovery_catalog.py` declares a small initial function set and formerly retained only the first two remote gateway hits, because larger fuzzy results were observed to cause model refusals. This performance protection unintentionally missed exact desired operations ranked third or later.
- `_process_user_request` previously truncated all remotely advertised tools to `tool_limit` before creating the available registry. This confused **catalogue availability** with **model-visible schema budget** and could make some installed gateways impossible to discover.
- `reasoning_policy.py` enforces eight reads/three rounds for standard and 12 reads/five rounds for investigative requests, useful to avoid runaway 30-tool calls, but an explicitly deep request sometimes needs a modestly larger controlled budget.
- `tool_registry.py`, `tool_executor.py`, confirmation policy and MCP server gates are essential and must remain the final execution authority. Neither prompt text nor model confidence substitutes for tool or server authorization.
- `final_answer_coordinator.py` already builds request-scoped evidence summaries, causal timelines and validators. That is a useful foundation; the priority is to ensure it has enough relevant evidence, not create more canned explanations.

## v0.17.6 implementation

- Preserve the complete **live, permission-filtered available tool registry** for discovery while preserving compact model-visible declarations.
- Prioritize exact operation names found in real `hub_search_tools` hits over incidental fuzzy hits without relaxing the broad two-gateway cap.
- Inject a concise, reusable Claude-skill-inspired operating contract into the existing system prompt. Add domain material only for relevant requests; defer tool details to the live MCP guide.
- For explicitly deep causal questions, carry proven event history and short evidence-bound attribution forward into the tool-planning/model reasoning path rather than finalizing immediately.
- Give those explicitly complex investigations at most 18 read calls/seven tool rounds; do not penalize ordinary quick controls or simple answers.
- Keep all writes protected by the same effect/confirmation/device identity pipeline and live server permissions.

## Remaining architecture to avoid one-off patches

**General evidence graph:** map the requested event to entities, commands, app/rule configuration, trigger events, conditions, timers and logs, with time windows, source completeness and strength. Explicitly mark verified, likely, conflicting, absent and not-checked evidence.

**Declarative investigation objectives:** e.g., verify event → command source → upstream trigger → conditions → alternatives. Let the model select the next *available* tool based on which graph edge is missing. Domain handlers should normalize facts and enforce safety, not author the final narrative.

**Dynamic tool capability registry:** optionally cache current `hub_search_tools` sub-tool metadata, schema samples and `hub_get_tool_guide` sections by version, retaining source provenance and respecting disabled tools. Expose a small rotating tool set per stage, not all MCP schemas simultaneously.

**Confidence and completeness:** distinguish “no event reported in these 50 rows” from “nothing happened”; detect clipped history and unavailable tools. Set explicit stop reasons: sufficient, budget, missing permission, conflicting evidence, or tool failure.

**Testing:** create a fixed multi-domain evaluation set for devices, modes, button controller, sensor history, Rule Machine, classic apps, scheduled jobs, integrations and permissions. Compare useful-answer completeness and correctness against Claude using the same access and timestamps. Track wrong-tool, unsupported-cause, over-fetch, blocked-write, and time-to-answer rates.

**Provider compatibility:** verify tool-calling fidelity of the chosen local/cloud model. Improving the host orchestration cannot make a weaker model understand complex scenarios exactly like a stronger model.

The aim is substantially fewer bespoke patches, not a promise of zero future changes.
