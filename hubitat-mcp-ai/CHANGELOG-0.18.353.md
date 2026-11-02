# Hubitat MCP AI v0.18.353 — progress-gated no-tool evidence checkpoints

## Generalized Q3 source-round consolidation
Previously independent no-tool recovery branches could each request another model round even when no distinct successful source read had occurred since the last checkpoint. A request-local `SourceCheckpointBudget` now caps these **source-choice** retries at three and permits another only after a new, successful, distinct, read-only scope.

The same budget is shared by target-history, upstream-input, inventory, configuration semantics, causal provenance, diagnostic discriminator, driver/controller evidence, source coverage and progress follow-ups. Existing specialized source admission, catalog/schema/effect validation, device and app ID verification, safety guards, and model-written final explanations remain authoritative. Failed, duplicate or write-class receipts never rearm a retry. This changes source-choice *model prompts*, not the independent model's tool-call rounds, actual MCP retries or final source reconciliation.

## Test evidence and limitations
Anonymous offline receipt timelines exercise zero-progress, duplicate scopes, newly successful source classes, failed or write receipts, request isolation, and the three-offer ceiling. The full CI and container gate must pass on the exact PR head before merge. No live Hubitat/Home Assistant connections, configuration or commands were used.

**Measurement:** The source-retry ceiling is enforced in deterministic tests; a reduction in actual Ollama model rounds, elapsed latency, first-answer accuracy, grounded causal claims or Claude parity is **NOT MEASURED**. The prior v0.18.348 real Dehumidifier 1 trace (56.657 seconds, 11 rounds, 14 tools) is an unmatched historical baseline, not an A/B speed comparison. Further work remains to move independent candidate generators into a single pre-ranked source obligation plan and run same-source real/model replay.
