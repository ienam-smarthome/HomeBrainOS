# HomeBrainOS V2 alpha.58 — observe review stages before changing architecture

**Date:** 12 November 2026
**Starting version:** 2.0.0-alpha.57
**Candidate:** 2.0.0-alpha.58 (V2 only)
**Change class:** evidence and answer-quality instrumentation; no new reasoning prompts, tool routing, or runtime decision policy.

## Problem and current evidence

Three **controlled same-incident** first answers were scored against the original successful MCP receipts:
- alpha.55: **2/8**, an overconfident inference about external cause
- alpha.56: **6/8**, correct uncertainty about initiator, but broader negative command-history wording than supported
- alpha.57: **2/8**, the unsupported external-cause inference returned after a final audit marked `completed`

These non-independent comparisons differ in model stochasticity and in available source reads. They are **not an A/B experiment** and do not establish that alpha.57 worsened general performance or that its scope index caused the error. An additional prompt is not justified by these results.

The existing agent may produce:
1. An **initial completed draft**, before an optional source-sufficiency review.
2. A **post-source-review draft**, possibly after additional *model-selected* read-only tool calls.
3. A **post-final-audit answer**, after a tool-free model round with existing receipts.

Previously the private Technical JSON disclosed only the final answer, tool receipts and flags indicating the checkpoints ran. Thus we could not identify at which stage the agent added an unsupported claim.

## Implemented instrumentation

The normal Agent.answer loop now captures **completed answer prose** at existing boundaries, bounded to three redacted entries of at most 10,000 characters each. No hidden chain-of-thought, partial tool-call messages or internal model tokens are saved. The field `answer_stage_trace` appears alongside the existing final `answer` in private Technical JSON, with:
- `stage`: `pre_source_review`, `pre_final_audit`, `post_final_audit` or `post_source_review_without_audit`
- `answer` (redacted excerpt), `answer_truncated`
- `after_model_round`
- `tool_receipts_seen`, `successful_tool_receipts_seen`, `failed_tool_receipts_seen`

If no review was entered, the trace may be empty: normal simple question results are unchanged. When an audit fails/times out, its pre-audit draft remains the delivered fallback and the trace does not claim the failed model produced a new answer. The preexisting `final_claim_audit_status` describes that fallback separately.

**Privacy:** these original and intermediate model answers may still contain household details. Technical JSON is private user-facing diagnostic data and must not be uploaded to a public GitHub issue, PR, test fixture or CI log. The short excerpts are redacted by the existing safeguard but must not be regarded as publicly safe. The optional local-only script `hubitat-mcp-ai-v2/tools/inspect_answer_stages.py` prints only stage names, counts and whether text changed; it never prints source rows or the draft text.

**No changed behaviour:** no new model calls, altered prompts, source reads, fixed tool order, answer rewriting, quality gate, command permission, Hubitat app change, external recorder alteration, or V1 change. The original MCP response receipts remain intact.

## What an initial stage comparison can establish

- If `pre_final_audit` and `post_final_audit` differ **with the same receipt counts**, the final model round changed wording without new MCP reads. Review the corresponding claims against the original successful receipts to see if a grounded conclusion improved or regressed.
- If `pre_source_review` and `pre_final_audit` differ **and additional receipts arrived**, the change cannot be attributed solely to the extra reasoning instruction: evidence availability changed too. Evaluate the incremental receipts and source completeness.
- If a stage already contains an unsupported claim and the later audit repeats it, the audit failed to correct that error; the audit need not have introduced it.
- If the later audit introduces a stronger unsupported claim, the specific same-run revision is observable. It is **not** proof that adding the pass caused the error across other model seeds or cases.
- If a previously correct answer becomes nonresponsive, or a positive command issuer disappears, mark that degradation explicitly. Uncertainty must not erase direct positive evidence.
- A status `completed` proves only a review round returned text, **not** that any claim was checked or verified.

## Evaluation protocol — do not tune on each failure

1. First run CI and install only after release verification. Confirm V2 add-on/API/UI match `2.0.0-alpha.58`. Keep the original alpha.57 cases as **regression controls**, not fresh holdouts.
2. Collect at least **12 genuinely new read-only first-answer questions** spanning causal device events, native rules, sensor/temperature histories, power/energy, hub health and sparse sources. Avoid follow-up coaching. Lock the question and requested proof conditions before seeing the response.
3. For each capture, preserve the original successful MCP receipts and any rejected tool calls. Score **each stage**, not just the final, using 0/1/2 for factual grounding, source completeness, causal calibration and usefulness; use N/A only if genuinely inapplicable.
4. Explicitly distinguish observed facts from command issuer, reporter, triggered listener, internal decision, historic configuration and absent evidence. Check source filters, caps, interval windows, event-time chronology, measurement freshness, positive commands and live tool errors.
5. Record which stage first makes any overbroad definite or negative claim, and whether added **tool receipts** materially changed what could be concluded.
6. To estimate a causal effect of an additional model pass, a separate future **paired experiment** is still needed: fixed original evidence/receipts, same model and question, counterbalanced condition order, multiple repetitions, blinded human scoring, no live device writes and exact cost/latency reporting. The observational stage trace alone does not establish this effect.
7. Do not promote V2 over V1 until cross-domain Gate B and live acceptance pass. If the final pass repeatedly worsens supported claims **without any new source evidence**, consider disabling or removing that pass **after** paired evaluation—not stacking another compulsory audit.

### Success criterion

Demonstrate a positive quality delta from review stages across the independent set while preserving direct facts and read-only safety, and quantify the extra latency/rounds. If evidence remains inconclusive, retain the simpler working default and document the uncertainty.

**Non-claims:** no independent live hub read, model-provider evaluation, multi-pass efficacy result or production cutover occurred as part of this instrumentation change.
