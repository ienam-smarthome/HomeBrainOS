# v0.18.17 — Evidence-aware finalisation and mixed-model continuity

## Live failures addressed
The explicit paid-model Bedroom 3 Mesh investigation used six DeepSeek V4 Pro rounds, then three Gemma rounds because the local conservative reservation ledger was at $2.852/$3 and could not reserve a further $0.1696. The final report marked three Hubitat source classes complete while the root cause was unresolved. It also discarded evidence of its successful full driver-source retrieval (code ID 3686, 20,531 source-offset units) when projecting the safe typed device report. The exact wording "Compare the most plausible causes" did not activate the cross-domain hypothesis planner.

## Improvements
- Extend the **existing** explicit comparative-investigation classifier to include "compare the most plausible causes", "compare the likely explanations" and "compare the root causes", without matching incidental mentions of "possible alternative causes". This allows the v0.18.15 model-proposed competing hypotheses to survive the v0.18.16 evidence-safe final answer. No extra planning work for ordinary fast-path causality.
- Keep source category checks and actual root-cause verification as **separate contract fields**: `sourceChecksComplete`, `rootCauseVerified`, and `questionResolved`. Existing `evidenceComplete` domain contracts are not silently redefined or upgraded. The host does not assert endpoint power or MQTT transport from a successful Hubitat call.
- When a targeted device investigation retrieved actual full/partial driver source, retain **bounded source-retrieval metadata** and a qualified retrieval-only note after the typed safety projection. Retrieved code is not proof of any driver's runtime branch or root cause; no raw model-generated causal narrative is promoted.
- Report explicit paid-model continuity: paid rounds, free rounds *after* paid, mixed-model completion, whether the local reservation ceiling blocked later paid rounds, and distinguish cumulative conservative HomeBrain estimates from Ollama's actual charges. If an explicit paid test switches to free after reaching the reservation cap, report that in the final answer instead of silently saying only "model: Gemma".
- No automatic resetting, lowering or reimbursement of paid reservations, no increase to spending limit, no API billing integration and no changing paid-model selection defaults.

## Tests
Regression tests cover the exact paid-test wording, ordinary causal route preservation, six-DeepSeek/three-Gemma mixed final answer with rejected $0.1696 reservation, no false mid-stream block announcement, complete driver-source metadata surviving final projection, and fail-closed incomplete source handling.

## Scope / future work
This fixes the handoff and observability gaps, not the larger goal of model-independent evidence fact attribution, typed contradictory-evidence ranking or source-code control-flow analysis. Future improvements should only rank hypotheses from independently matched scoped observations and preserve all MCP permission and confirmation safeguards.

GitHub CI required before merge; end-to-end Home Assistant and Hubitat MCP validation is still required.
