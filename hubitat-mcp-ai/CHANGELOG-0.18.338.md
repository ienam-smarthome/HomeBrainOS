# v0.18.338 — authentic first-model-draft provenance (model-first publication foundation)

## Evidence
The user's v0.18.337 read-only single-device investigation used Ollama Cloud `gemma4:31b`: **11 model rounds**, **11 recorded tool calls**, **46,924 ms provider**, **59,698 ms agent** and **61,224 ms observed wall time**, yet the final message remained a deterministic source-typed summary. The live coverage said `publicationBoundaryShadow.replacementPerformed=true` and `incomingVerifiedRawModelDraft=false`, so we previously could **not** tell whether the incoming answer was genuine unmodified model prose or a rewritten coordinator/fallback. This is the architectural blocker; testing different model prompts against a postprocessed string is invalid.

## Runtime architectural changes
- `model_first_draft_provenance.py` creates a **request-local ContextVar** at the orchestrator boundary and captures the actual first no-tools model completion **immediately after the provider call**, before focus repair and `validate_synthesis`.
- Track separately the synthesis coordinator's validated/repaired result, the author-boundary guarded result, and the incoming API completion response. Copy this private provenance through `AgentOutcome` and `ObservedAgentOutcome` without serializing raw text or storing private hashes, source IDs or timestamps.
- The shared typed-history publisher reports only fixed booleans under `investigation_coverage.modelFirstDraftBoundary`: first draft captured, coordinator captured, unchanged/changed across each boundary, and whether published prose equals the **actual first model draft**. Values are strict literal equalities; they **do not grade answer quality**.
- The request-local capture resets on completion/failure, does not share state across concurrent requests, and is never used to grant a write or model assertion. Non-model/direct outcomes correctly report no first-draft proof.
- **No changes to publication admission yet.** `modelProseAuthorizedForPublication=false` and `rawDraftSourceClaimsAttested=false` remain honest until a general typed evidence-claim proof contract is implemented. Current source-grounded deterministic protection remains for offline/causal/physical claims. No new model/MCP rounds or home-system changes.

## Acceptance gates / tests
Privacy and concurrency tests check initial draft versus repair versus author guard, model-free routes, async request isolation, that `repr` and serialized API omit raw draft/credentials, and that even a deliberately fabricated raw model claim cannot override the source-grounded telemetry publisher. Full Python, smoke, metadata and dedicated offline-scorecard CI must pass on the exact PR head.

**Status:** Structural model-first foundation, not yet free-form model-first publication, better factual accuracy, reduced provider latency, or Claude parity. Quality scorecard **NOT MEASURED**. Next stage: source-linked claim/witness admission with cross-domain (telemetry, lighting, heating and explicit negatives) fail-closed evaluation; only then enable publication of truly model-authored natural prose. Do not treat citation labels or lexically matched facts as sufficient validation. If provenance transition was altered by upstream rewriting, candidate must fail closed.

## Rollback
Remove request-local field/capture, the final coordinator record hook and privacy-safe telemetry boundary metrics. Source-backed publication remains unchanged.
