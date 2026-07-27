# HomeBrainOS architecture

## Current add-on

- `hubitat-mcp-ai/` is the maintained and only Hubitat MCP assistant. The
  legacy Maker API dashboard and assistant (`homebrainos/`) has been retired
  and removed from this repository.

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
  superseded compatibility modules have been removed. The cluster analyzer
  explicitly recognizes `ollama_agent_fast` and `ollama_agent_inference` as
  intentional documented layers; other sibling-only modules remain suspect.
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
  washing-rule compilation, backup preflight/confirmation, filename safety,
  write recovery and repair safety are consolidated behind the externally wired
  `automation_rule_workflow_repair_id_safe.py`.
- `fast_fallback_*`: the base, weather and live-state kernel is consolidated in
  `fast_fallback_live.py`; verified control, attention, group control,
  device-health and speech behavior is consolidated in
  `fast_fallback_device_health.py`; inventory, dashboard, room, status and
  extended-read behavior is consolidated in `fast_fallback_extended_reads.py`;
  prayer-time, device-type, index, engagement, multi-control and light-usage
  behavior is consolidated in `fast_fallback_light_usage.py`. All four
  remaining family modules are wired outside the family.
- `home_snapshot.py`: owns the base, truthful-state recovery and hybrid
  Cloud-first snapshot services in one canonical module. The three public
  service classes and installer functions remain available without a
  sibling-only inheritance chain.
- `device_intelligence_catalogue.py`: owns capability enrichment,
  authoritative selected-device membership, safe state merging, dashboard
  metrics, duplicate-name diagnostics and conservative spoken-name matching.
- `conversation_context.py`: owns the conservative per-session context store
  and installer, including stale-pronoun clearing, reordered comparisons and
  room-name-safe follow-ups.
- `webui_*`: the base HomeBrain renderer, mobile dashboard, clipboard fallback
  and HTTP error handling are consolidated in `webui.py`; feature-specific UI
  patchers remain separate modules.

Use `scripts/analyze_imports.py` and `scripts/analyze_clusters.py` before changing these families.

## Import graph health

The add-on has 115 production Python modules, all reachable from a
declared entrypoint. `scripts/analyze_imports.py` reports zero orphans.

`scripts/analyze_clusters.py` distinguishes same-family inheritance from plain
module composition. Unlisted sibling-only subclass layers remain suspect;
ordinary function composition, such as `semantic_home_summary_agent.py` using
`semantic_home_evidence.py`, is reported as live.

The former `sitecustomize.py` compatibility hook was retired after structured
MCP result handling moved into `mcp_client.py`; Python's implicit
`sitecustomize` loading therefore no longer hides behavior from the static
import graph.

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
4. [done] Consolidate automation Rule Machine safety layers behind the native,
   washing and externally wired recovery owners.
5. [done] Merge fast-fallback near-duplicates by semantic capability.
6. [done] Fold Web UI safety wrappers into a single maintained Web UI implementation.
7. [done] Replace the unified-agent `application.ask` monkey-patch with an
   explicit maintained request-layer composition.
8. [done] Fold capability-catalogue safety and duplicate-aware matching into
   `device_intelligence_catalogue.py`.
9. [done] Fold conservative follow-up handling into
   `conversation_context.py`.
10. [done] Distinguish subclass accretion from ordinary sibling composition in
    the cluster analyzer.

Each phase must preserve current public commands, MCP safety behaviour and Home Assistant startup.

## Request-handler composition

`entrypoint_core.py` is the maintained owner of the live request pipeline. It
captures the complete control-agent and legacy route stack, builds the unified
MCP agent as a pure handler layer, and assigns the composed handler once.

`request_composition.py` provides the typed, named layer primitive and records
the declared outer-to-inner order for diagnostics. The compatibility installer
in `mcp_agent_orchestrator.py` remains available for isolated callers and tests,
but the production entrypoint does not use its mutation-based API.

`entrypoint.py` uses `AskCompositionBuilder` for every auxiliary request
installer. The builder captures compatibility wrappers, preserves their service
return values and non-request side effects, rejects untracked mutations, then
verifies the reconstructed typed chain is the same live handler before
finalizing it. Service-only installers remain direct calls because they do not
participate in request ordering.

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
