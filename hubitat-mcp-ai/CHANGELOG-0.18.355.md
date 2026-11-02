# Hubitat MCP AI v0.18.355 — post-grounding evidence-source proposal consolidation

## Hypothesis
Four independent no-tool recovery branches (diagnostic discriminator, unchecked required source, installed driver/controller, and incident progress) duplicate candidate priority and checkpoint invocation logic. A shared fixed-priority selector can retain the same admissible evidence sources without moving work before the existing grounding decision, adding permissions, or replacing the model's natural answer.

## Scope
- Extend the existing `evidence_first_source_followup.py` with a second **fixed**, reviewed source order and a read-view-only candidate that can use the current investigation read view without adding gateways.
- Replace the four sequential post-grounding branches in `mcp_agent_orchestrator.py` with one lazy source-choice plan. The original source-specific predicates and evidence renderers remain authoritative: the same existing app/driver status conditions, `necessary=true;state=not-checked` assessment, prior attempt flags, model round boundary and request-wide source-progress budget continue to apply.
- Keep original discovery/catalog availability checks and do not broaden any exposed gateway. Missing required source uses **only** the currently admitted read-view, not the broader diagnostic gateway set. Apply successful source-specific flags and metrics after selection.
- Leave configuration semantics **before** grounding, and task coverage / causal provenance fallbacks **after** this selector; this preserves the safety and checked-but-empty / incomplete-evidence boundaries.
- Keep control permissions, mandatory final source completion and model-generated prose unchanged. No live Hubitat or Home Assistant calls, controls, configuration or automations are changed by this development work.

## Offline before/after verification and limits
`tests/fixtures/q3_late_source_replay_v1.json` freezes **13 anonymous synthetic** candidate packets, including checked-but-empty, missing/unavailable read view, failed progress, source priority and exhausted budget. Tests compare a separate emulation of the prior source ordering with the unified selector on **the same inputs**, assert lazy fallback and no mutating gateways, and confirm the orchestrator integration stays downstream of grounding. This is a selector-equivalence regression check, **not a user answer benchmark**.

**Live answer-quality, median/p95 latency, model-round savings and Claude comparison remain NOT MEASURED.** The latest previously captured installed v0.18.348 trace took 56.657 seconds/11 model rounds/14 tools; it is not a valid same-evidence A/B speed comparison with v0.18.355.

## Remaining work
The final semantic-source-coverage and causal-provenance model retries still sit outside the shared candidate plan because they control distinct incomplete-evidence fallback and read-only provenance phase transitions. Before claiming user-facing improvement, perform a source-complete, same-evidence model replay and human first-attempt review; do not repeat exhausted household incident probes or invent source-based causal certainty.

Revert this PR if CI or reviewed source completeness regresses. Require all GitHub checks green at the exact head before merge.
