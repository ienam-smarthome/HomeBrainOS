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

- `ollama_agent_*`: live entry is `ollama_agent_unified.py`; ancestors provide inherited behaviour.
- `control_agent_*`: several directly wired capabilities currently coexist.
- `automation_rule_workflow_*`: native Rule Machine workflow composes several safety layers.
- `fast_fallback_*`: many read/control capabilities form a dependency chain.
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

1. Remove confirmed zero-importer production modules.
2. Flatten the Ollama inheritance chain behind `UnifiedAdaptiveMCPAgent`.
3. Consolidate overlapping control-agent wrappers behind one public control service.
4. Consolidate automation Rule Machine safety layers.
5. Merge fast-fallback near-duplicates by semantic capability.
6. Fold Web UI safety wrappers into a single maintained Web UI implementation.

Each phase must preserve current public commands, MCP safety behaviour and Home Assistant startup.

## Ollama runtime wiring

`app.py` currently constructs a `ClaudeStyleOllamaAgent` during module import.
`entrypoint_core.py` then replaces `application.ollama` with the live
`UnifiedAdaptiveMCPAgent` before the request-serving application is exposed.

The temporary base-agent construction is retained for now because changing
startup composition and flattening the inheritance chain in the same release
would increase regression risk. `tests/test_ollama_runtime_wiring.py` pins the
final runtime class before that cleanup begins.

The next Ollama consolidation phase must:

1. preserve `UnifiedAdaptiveMCPAgent` as the final request-serving object;
2. determine whether construction of the temporary Claude-style agent can be
   removed without losing shutdown, fallback or configuration behaviour;
3. add behaviour-level tests before removing shadowed ancestor methods;
4. flatten one inheritance layer at a time rather than deleting the chain in
   one change.

## Deferred Ollama startup

The maintained `entrypoint_core.py` startup now requests deferred legacy Ollama
initialization before importing `app.py`. During that import, `app.py` installs
a lightweight temporary object rather than constructing a complete
`ClaudeStyleOllamaAgent` and unused HTTP client.

`entrypoint_core.py` then replaces the placeholder with
`UnifiedAdaptiveMCPAgent`, as before. Direct standalone execution of `app.py`
continues to construct the Claude-style agent for compatibility.

This removes duplicate startup work without yet changing the load-bearing
Ollama inheritance chain.
