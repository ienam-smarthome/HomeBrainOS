# HomeBrainOS v2 — first real-source ledger A/B pilot results

**Recorded:** 10 November 2026  
**Development status:** Two-case, manually rated pilot completed. **Do not promote the experimental source ledger.** This is a descriptive evaluation result, not a controlled demonstration of causal reasoning or a verified improvement.

## Experiment and evidence

The user supplied the private, per-case source-real first-answer exports and the privacy-safe aggregate report from the opt-in alpha.27 **Real-source A/B** runner. Both frozen pairs were completed, manually rated and unblinded. Case `new-01` investigated voltage attribute coverage in returned device states; case `new-02` investigated installed application status and the distinction between paused rules, disabled apps and enabled apps. These questions are **now exposed** and must not be reused as new unseen acceptance cases after any adjustment.

The aggregate report contains no original device names, raw household records or credentials. Its flags explicitly state that model accuracy, matching source snapshots and per-token enforcement were **not independently verified**. The per-case private source receipts supported a provisional manual review, but source-real first-answer quality was not certified by an independent evaluator. For `new-02`, the two arms retrieved materially the same app and Rule Machine inventory. Neither case asked for an investigation of event causation, so **causal calibration has no rated denominator**.

## Unblinded aggregate scores

Each answer was rated from 0 to 2 for factual grounding, source completeness and usefulness. Two answers per condition give a maximum of 4 in each scored dimension.

| Measure | Unchanged baseline | Experimental collection ledger | Interpretation |
| --- | ---: | ---: | --- |
| Factual grounding | 3/4 | 2/4 | Candidate lower by 0.5 points per pair on average |
| Source completeness | 3/4 | 2/4 | Candidate lower by 0.5 points per pair on average |
| Usefulness | 2/4 | 3/4 | Candidate higher by 0.5 points per pair on average |
| Causal calibration | Not rated | Not rated | Both cases marked not applicable |
| Native tool attempts | 5 | 6 | Candidate used one additional call |
| Tool attempts reported failed | 1 | 1 | Equal |
| Response-time paired median | Baseline reference | Candidate **+462 ms** | Candidate slower in this tiny pilot |

Candidate-vs-baseline pairwise wins/ties: factual grounding **0 better / 1 worse / 1 tied**; source completeness **0 better / 1 worse / 1 tied**; usefulness **1 better / 0 worse / 1 tied**. The aggregate `model_accuracy_independently_verified`, `matching_live_source_snapshots_verified` and `token_enforcement_independently_verified` fields remain **false**, so avoid treating any of these as externally certified outcomes or a proven token-enforcement test.

## Case-level findings (no private receipts reproduced)

- **new-01 — generic field inventory:** Baseline was **B**, candidate **A**, inferred by combining the disclosed aggregate direction with the saved blind scores. Both counted incorrectly. Baseline B recognized the authorized-state boundary and distinguished reported zero voltages from missing fields; it nonetheless reported 14 readings although the 15-item list and private receipt check supported 15. Candidate A conflated capability matches with returned voltage attributes and assumed an all-device inventory proved full current-state coverage. This exposed **generic aggregation and source-scope interpretation failures**, not a voltage-specific condition to patch.
- **new-02 — app and rule statuses:** Baseline was **A**, candidate **B** by the same inference from saved blind ratings. Both correctly separated a paused Rule Machine rule from disabled app instances and broadly acknowledged that `disabled:false` is not independent proof an app is executing. Candidate B provided a more precise numerical breakdown and scored one point higher on usefulness. Factual grounding and source coverage were tied.

Per-case condition allocation is reconstructed from user-provided score cards and the aggregate direction; the **aggregate JSON does not itself publish per-case allocation**. The above descriptions are for diagnostic continuity, not a replacement for the original private exports.

## Decision and next gate

**Reject promotion on current evidence.** This prototype did not improve the primary attributes of grounded claims or source completeness in the two-case pilot; its small usefulness advantage is insufficient. No conclusion about causal reasoning can be drawn because there were zero causality ratings. The standard v2 Ask route continues to instantiate the **unchanged baseline Agent**, while the source-ledger implementation is confined to the opt-in experimental interface.

Before a new promotion decision, use a freshly frozen, independently capability-validated and read-only **causality-focused**, cross-domain comparison with more cases, verified source provenance and explicit claim-level assessment. Include command-versus-state evidence, source-window limitations, ambiguous automation attribution, and unavailable evidence; do not hand-patch old voltage/app scenarios or score the old exposed `hold-..`, `sr-..`, or `new-01/02` questions as unseen. Consider independently testing generic numeric evidence validation before proposing another source-presentation intervention.

**Safety:** No repository documentation change alters MCP tokens, active device controls, model routing or normal Ask. The operator previously observed a dedicated read-only client grant; the report appropriately does not call that an independently tested token enforcement guarantee.
