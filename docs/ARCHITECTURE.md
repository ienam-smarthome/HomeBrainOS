# HomeBrainOS architecture

## Current add-ons

- `hubitat-mcp-ai/` is the maintained Hubitat MCP assistant.
- `homebrainos/` is the legacy Maker API dashboard and assistant.

The maintained assistant starts at `hubitat-mcp-ai/rootfs/app/entrypoint.py`, composes the established services from `entrypoint_core.py`, and rebinds the final FastAPI routes through `runtime_route_bridge.py`.

## Request flow

1. **Safety-critical deterministic routes** handle explicit controls, confirmations, named app/rule writes, firmware operations and exact authoritative reads.
2. **Semantic home routing** maps broad natural-language questions to stable semantic intents rather than matching every possible phrase.
3. **Evidence services** read Hubitat through MCP and return typed facts, counts and exact entity names.
4. **AI synthesis** turns verified evidence into natural wording.
5. **Fact validation** rejects AI output that omits or changes required facts and falls back to deterministic natural wording.
6. **Presentation and tracing** add display metadata and technical diagnostics without changing authoritative facts.

## Live semantic home modules

- `semantic_home_query_router.py`: AI intent classification for broad whole-home questions.
- `semantic_home_evidence.py`: typed current-home facts from the selected device inventory.
- `semantic_home_summary_agent.py`: validated natural-language synthesis and deterministic fallback.

New phrasings should normally be handled by semantic intent classification. Regex is reserved for explicit safety-sensitive commands, confirmations and narrow latency optimisations.

## Major module families

Several older areas are implemented as load-bearing inheritance or wrapper chains. They must be flattened incrementally with regression tests rather than deleted by filename:

- `ollama_agent_*`: consolidated live chain is `fast → inference → claude → unified`;
  superseded compatibility modules have been removed.
- `control_agent_*`: core confirmation state, base execution, verified-level
  control and rescue behavior are consolidated in `control_agent_rescue.py`;
  actuator eligibility and read-only-device safeguards are consolidated in
  `control_agent_graph.py`; Claude-first, goal-based, semantic-target and
  combined-level interpretation are consolidated in
  `control_agent_combined_level.py`. All remaining family modules are wired
  outside the family.
- `automation_rule_workflow_*`: live schema, release safeguards and native Rule
  Machine execution are consolidated in
  `automation_rule_workflow_native_rm.py`; notification discovery, guarded
  washing-rule compilation and final backup preflight are consolidated in
  `automation_rule_workflow_washing.py`; backup confirmation, filename safety,
  write recovery and repair safety remain to be consolidated.
- `fast_fallback_*`: the base, weather and live-state kernel is consolidated in
  `fast_fallback_live.py`; verified control, attention, group control,
  device-health and speech behavior is consolidated in
  `fast_fallback_device_health.py`; inventory, dashboard, room, status and
  extended-read behavior is consolidated in `fast_fallback_extended_reads.py`;
  prayer-time, device-type, index, engagement, multi-control and light-usage
  behavior is consolidated in `fast_fallback_light_usage.py`. All four
  remaining family modules are wired outside the family.
- `home_snapshot_*`: `home_snapshot_hybrid.py` is the live entry and builds on truthful snapshot behaviour.

Use `scripts/analyze_imports.py` and `scripts/analyze_clusters.py` before changing these families.

## Consolidation rules

1. Confirm the live import graph before moving or deleting code.
2. Port missing safety checks from a superseded layer into the selected implementation.
3. Add regression tests before removing the old layer.
4. Change imports to the consolidated module.
5. Run focused tests, repository validation and the release gate.
6. Delete the superseded file only after no production or test importer remains.
7. Use Git history for old implementations; do not keep `_final`, `_safe`, `_v2` or `_verified` copies unless they remain distinct live capabilities.

## Planned consolidation order

1. [done] Remove confirmed zero-importer production modules.
2. [done] Flatten the Ollama inheritance chain behind `UnifiedAdaptiveMCPAgent`.
3. [done] Consolidate overlapping control-agent wrappers behind maintained
   public control services.
4. [in progress] Consolidate automation Rule Machine safety layers; the live
   schema/release/native and notification/washing groups are complete.
5. [done] Merge fast-fallback near-duplicates by semantic capability.
6. Fold Web UI safety wrappers into a single maintained Web UI implementation.

Each phase must preserve current public commands, MCP safety behaviour and Home Assistant startup.

## Ollama runtime wiring

`entrypoint_core.py` installs `UnifiedAdaptiveMCPAgent` as the final
request-serving object. The maintained inheritance chain now contains four
behavior-bearing layers: `ollama_agent_fast`, `ollama_agent_inference`,
`ollama_agent_claude` and `ollama_agent_unified`.

Consolidated behavior is pinned by `tests/test_ollama_agent_live_chain.py`.
Historical behavior-level tests import the live owner directly rather than
keeping compatibility modules solely as test adapters.

## Deferred Ollama startup

The maintained `entrypoint_core.py` startup now requests deferred legacy Ollama
initialization before importing `app.py`. During that import, `app.py` installs
a lightweight temporary object rather than constructing a complete
`ClaudeStyleOllamaAgent` and unused HTTP client.

`entrypoint_core.py` then replaces the placeholder with
`UnifiedAdaptiveMCPAgent`, as before. Direct standalone execution of `app.py`
continues to construct the Claude-style agent for compatibility.

This removes duplicate startup work while preserving the consolidated
four-layer Ollama chain.
