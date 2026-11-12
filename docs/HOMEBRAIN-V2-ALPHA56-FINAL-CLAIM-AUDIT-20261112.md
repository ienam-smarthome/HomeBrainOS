# HomeBrainOS V2 alpha.56 — final source-to-claim contradiction audit

**Date:** 12 November 2026  
**Starting version:** 2.0.0-alpha.55  
**Candidate:** 2.0.0-alpha.56 (V2 only)  
**Scope:** model-led response evidence calibration; read-only followups remain model-selected.

## Why this candidate exists

Three private alpha.55 first-answer reviews, each scored against the original successful source receipts, received **4/6**, **5/6**, and **2/8** under the established factual-grounding / source-completeness / causal-calibration / usefulness rubric (N/A only where truly inapplicable). These non-random captures do **not** quantify model accuracy or prove cross-version improvement.

Two review cases showed helpful typed-status and sensor-freshness distinctions but overbroad negative descriptions. A causal case was more severe: the model correctly returned a state-change time, state reporter and current automation configuration, then concluded definitively that initiation was external and that the hub did not command the action. Its bounded filtered event reads, short unfiltered window and narrow text-matched logs did not prove either absence, while the supplied source scope explicitly disallowed external-initiation inference from a bridge/physical state report.

The first source-sufficiency checkpoint already warned against this reasoning pattern. The remaining general problem is **final-answer source/claim contradiction**, not a missing device-specific rule or a need to force a tool sequence.

No private Technical JSON, local device identities, app identifiers, LAN addresses, credentials, personal event history, or timestamps have been copied into this public document or the regression fixtures.

## Implementation

1. Keep the existing natural model investigation and optional source-sufficiency checkpoint. The model remains responsible for deciding which source to read, with the existing read-only tool catalog at that checkpoint.
2. After that review and any model-selected read-only followups, allow **one extra tool-free final model pass** when a draft exists and the remaining deadline exceeds 12 seconds. It receives the existing original receipts and its preceding draft and is asked to compare definitive statements directly against source boundaries, including query filters, row caps, lookback, reporters, initiators, positive command issuers, negative claims, cached measurements and UI-only controls.
3. The final pass produces the user-facing answer in the model's own words. The host does not classify claims, introduce source-specific causal rules, rewrite prose or infer incident causes.
4. No tools are advertised during the final audit. Unexpected tool calls cannot execute. If the audit model fails, requests a tool, gives an empty reply or runs out of time, return the previously completed draft with explicit status metadata rather than losing the user's usable result.
5. Add `final_claim_audit_invoked` and `final_claim_audit_status` to successful Technical JSON. Status examples are `completed`, `skipped_low_time`, `model_error_fallback`, `deadline_fallback`, `tool_request_fallback`, `empty_response_fallback`, and `not_invoked`. A completed audit is **not a certification of factual correctness**.
6. Preserve the private installed-run / published source distinction and the original V1 add-on, monitor recorder, native Hubitat permissions, confirmation checks, normal tool choice, and historical receipt contents.

This deliberate additional model round adds latency for reviewed questions; short status requests and unreviewed flows do not gain an extra round. The pre-existing source-review checkpoint still gates on sufficient remaining time and available read-only tools.

## Fictional regressions and validation

Synthetic orchestration tests cover:
- A bridge-reported OFF event with no returned command row; a scripted model's earlier overconfident 'external' conclusion can be challenged without any extra MCP call.
- A real fictional `command-off` row whose recorded issuer and time must remain visible, even if the internal controller decision remains unverified.
- A failed final model round returning the previous completed answer with a truthful fallback status.
- An unsolicited tool request during tool-free audit never executing, even if it names an otherwise valid read-only tool.
- Existing source-review tests retain their original single-checkpoint semantics, and separate alpha.56 tests exercise the new default round.

These tests verify orchestration, prompt delivery and safety boundaries; **scripted replies do not prove a particular cloud model will self-correct.** Full V2 Python, browser and add-on CI should pass before merge/release. Test the installed `2.0.0-alpha.56` UI/API/add-on separately; a merged PR cannot prove the installed runtime was updated.

## First-answer acceptance

Use fresh uncoached read-only questions in multiple domains, comparing original successful receipts rather than the proposed reasoning or source-index headings. Verify:
- Exact event timestamps and chronology; which event types/attributes were queried, with what windows and caps.
- Reporter versus command issuer versus internal controller decision, including *positive* issuers that must not be concealed.
- Distinguishing no returned command/log rows from proving no action occurred.
- Historical saved sensor-bin freshness and what the source does and does not establish about physical observations.
- Rule status from typed properties, stored pointer versus independently verified parent, and config versus execution.
- Actual `final_claim_audit_invoked`, `final_claim_audit_status`, elapsed time, model rounds and tool errors.

Score factual grounding, source completeness, causal calibration and usefulness 0/1/2. Do not treat a coached test, same-device replay or synthetic suite as an independent blinded holdout. Keep all Technical JSON private. Prefer a new cross-domain Gate B sample before V2 cutover.

**Non-claims:** alpha.56 does not prove where a prior device event originated, guarantee that the cloud model will reject all overclaims, add new source records, authorize writes, or close the V1-to-V2 acceptance gap.
