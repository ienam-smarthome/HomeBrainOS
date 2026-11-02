# Hubitat MCP AI v0.18.354 — unified early source-choice proposals

## Q3: one evidence-first proposal path for target/history/input/inventory
Three independent no-tool recovery branches previously competed in the model loop: target-scoped history, upstream input/source and inventory-only diagnosis. They now feed a **single priority-preserving source-choice coordinator**, before the model decides which read-only tool to use. Existing source-specific admission functions are still responsible for verifying whether a source gap exists; the coordinator does not infer devices, events, decision reasons or permissions.

- Exactly one source-choice offer is selected per existing source-progress epoch, using the v0.18.353 bounded request-local budget.
- **Target scope > upstream input > inventory evidence** retains the previous branch precedence; source generators are lazy and lower-priority generators are not called once an earlier source is admitted.
- The selected source uses the same original read-only catalog gateway exposure and diagnostic metric; inventory-only fallback remains an honest partial result when further investigation cannot be grounded.
- Explicit read-only gateway allowlist rejects candidate plans containing write-capable gateway names, even if the candidate kind was mislabelled.
- Natural model-authored final answers and mandatory final source reconciliation remain unchanged. No added model round or live Hubitat/HA change.

## Frozen offline replay and limitations

The synthetic/anonymised `q3_early_source_replay_v1.json` input set freezes eight source-choice conditions across historical causality, heating, lighting, ventilation, network, sensor and status domains. Tests compare an independent v0.18.353 branch-order reference with the new single plan on **the same candidate prompts, admission flags and successful-read receipt scopes**. This establishes selector consistency/coverage only. The fixture has no real model transcript and cannot certify first-answer accuracy, speed, true device causation or Claude quality.

Expected measured selector result: 8/8 cases equivalent to original branch order; full Python, container, metadata, release and validation CI must pass on exact head. No production A/B Ollama latency or human-reviewed factual score exists; all user-facing answer-quality improvements remain **NOT MEASURED**. The latest documented real installed trace remains an older v0.18.348 56.657-second / 11-round / 14-tool investigation, not a before/after comparison.

## Remaining roadmap
Continue consolidating the later evidence-gap source candidates into the same obligation plan *after* mandatory safety and grounding checks, without losing source-completeness warnings. Run a same-packet model replay with source identities and decision provenance before claiming any actual output improvement.
