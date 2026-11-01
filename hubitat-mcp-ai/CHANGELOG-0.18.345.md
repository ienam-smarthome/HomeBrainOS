# Hubitat MCP AI v0.18.345 — rollback to v0.18.343 answer behavior

## Why this release exists

The user reviewed a real v0.18.344 Bedroom 3 Mesh read-only answer and preferred the more natural previous model-led answer. The v0.18.344 reply had been replaced by the host's fixed concise evidence template after a conflicting-clock gate fired. The trace confirms the replacement was intentional (`answerPublicationDecision.mode=concise`, `modelFirstRejection=unresolved-source-clock-conflict`, `publishedIsFirstModelDraft=false`), not a new regression in Gemma itself.

**User request: restore previous behavior and stop testing Bedroom 3 Mesh.** This is a behavioral rollback, not a declaration that the earlier diagnosis was factually proven.

## Code changes

- Restore all six runtime modules touched by v0.18.344 to their exact v0.18.343 code: `model_first_publication.py`, `mcp_agent_orchestrator.py`, `source_authority_packet.py`, `driver_source_identity_guard.py`, `tool_executor.py`, and `request_metrics.py`.
- Remove the v0.18.344-only source-ID/source-read tests. The v0.18.343 source-authority packet and bounded target configuration read remain available.
- Remove v0.18.344's blanket conflicting-clock template override; restore opt-in model-authored telemetry prose when the original v0.18.343 admission checks allow it.
- Keep the `model_first_investigations_enabled` option **off by default**. Device commands and mutation permissions are unchanged.
- Publish as **v0.18.345**, not a reused or downgraded version number. Existing v0.18.344 release notes remain an accurate historical record.

## Validation, limitations and next evaluation

Run all repository checks at the exact PR head, including full Python tests, release metadata, container smoke and safety regression checks. A synthetic test confirms clock conflict alone no longer forces host prose replacement. These checks do not establish answer truth.

The prior v0.18.343 first-draft example was fluent but included unsupported broker-session and physical-silence claims. Restoring it fulfills the user's preferred presentation, **not** a factual-accuracy acceptance. Factual score and Claude parity remain NOT MEASURED. Do not add new case-specific phrase filters or test Bedroom 3 Mesh again.

Next read-only evaluations should cover **distinct domains** (e.g., Livingroom Light 2 OFF causality, heating protection/scheduler state, bathroom fan boost decision) with separate one-shot questions and full Technical JSON. Never change Hubitat or Home Assistant device state for these tests.
