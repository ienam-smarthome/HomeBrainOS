# v0.18.263 — V3 Stage C: source-feasible, non-redundant model-directed reads

## Live acceptance input: v0.18.262, 30 October 2026
- Native model `gemma4:31b`, 11 rounds, 31 tool calls, 55.45 s elapsed, 43.99 s provider processing, no recorded immediate target ON issuers.
- V3 witness shadow: 48 typed evidence witnesses, four source-timed input reports; two target devices still without matching command-on witness.
- Despite its 20 source-timed light switch reports, the model fetched an app source across four chunks (approximately 186K characters) and made several additional reads; the finalizer still replaced model text with the Historical Journal digest.
- The original incident explicitly lacked an independently verified command-origin/execution trace. `command_history` source category remained unchecked. Two `hub_get_logs` requests initially failed because of malformed arguments and were successfully retried. Source-code discovery checked Groovy source availability but did not establish a command-origin capability.

## What changed
- New pure `causal_source_feasibility.py` builds a short read feasibility packet from the previously landed V3 witness ledger, verified target identities, observed app command issuers, and successful **read-only** leaf operations already used by the same request.
- Emits concrete *advisory* read candidates only when the leaf was already successfully called: an unqueried named target's app dependents or unqueried recorded command-app configuration. The original model chooses whether to call; the current live MCP catalog still controls authorization.
- Aggregates successful **exact** read signatures to identify repeat work. A failed tool call followed by a repaired successful call is not incorrectly counted as a redundant success.
- Separates `original-ON-command-issuer not witnessed in retained evidence` from source-unavailable or command-absent claims. A prior Groovy-source tool search does **not** prove that a command-origin source was checked.
- Distinguishes unavailable original input source time from collector-reception co-occurrence; no timestamp threshold gains causal authority.
- Integrates the advisory packet into existing original-model `unified_investigation_instruction`, `unified_investigation_followup`, and `cross_source_discovery_checkpoint` without adding an independent planner, new MCP tool, hardcoded wording route, writes, or an unconditional stop.
- The existing evidence-grounded terminal fallback is intentionally unchanged until model responses can be validated against witnesses.

## Safety and limitations
Successful prior invocation only establishes that a leaf was usable in the sampled request; a later call still requires the model's active authorized READ catalog. Suggestions are not commands. Candidates are bounded to source-verified IDs. The absence of a candidate in the already retained receipts **does not** prove a source does not exist elsewhere. These are model guidance and replay tests, not proof the model's live tool calls will be reduced.

## Acceptance criteria
Tests demonstrate deterministic advisory options, no invented operations, invalid-identity exclusion, no success counting for failed retries, no false conclusion about command-history capability, positive issuer distinction, one checked source not repeated, and read-only prompt integration.

Next is live A/B comparison of actual tool calls, missing source checks, and natural-language explanation quality. Claim-level validation must precede any removal of the legacy finalizer.
