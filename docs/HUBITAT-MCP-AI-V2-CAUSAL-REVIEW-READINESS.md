# HomeBrainOS v2 alpha.28 — independent causal A/B acceptance

**Prepared:** 10 November 2026.  
**Status:** Engineering evaluation instrumentation, not evidence of model improvement. No new live Hubitat or model calls were run to build this feature.  
**Scope:** Optional alpha.28 Real-source A/B causal study only. Baseline Ask/Chat Agent is not modified; generic source-ledger candidate remains unpromoted.

## Why this is needed

The earlier two-case alpha.27 pilot found lower factual grounding and source completeness with the experimental source ledger and a small advantage in answer usefulness. Both questions concerned inventories, not event causality; the aggregate had **zero causal-calibration ratings**. The next acceptance study must be new and prospectively frozen, focus on causal claims, and report the actual evidence and missing source boundaries without an assistant inventing certainty.

## Operator safety preflight

- Continue using a separately configured, server-enforced **read-only MCP client token** on the actual v2 endpoint, rather than the main token. A global `writeEnabled: true` setting can coexist with client `clientAccess.writeEnabled: false`. Do not share endpoint credentials.
- The Real-source A/B **Check client access** action calls `hub_get_info` without a model. Every subsequent model arm repeats a fresh grant check, requiring token-specific Read ON and Write OFF. A missing or writable client grant fails closed.
- Only live tools explicitly annotated `readOnlyHint: true` and gateway leaves with the same annotation are exposed. This restriction is additional protection, not an independent write-permission enforcement test. No write probe is attempted.
- Freeze and score only real incidents/events selected with verified existing hub targets and valid capabilities. No Rule Machine writes, device commands, Home Assistant changes or background evaluation. The run is manually initiated and cloud inference may consume credits.

## Freeze a NEW causality-oriented study

1. Refresh/reinstall the add-on to **2.0.0-alpha.28** and reopen the interface. Confirm version in the header. Keep **Causal evidence study** ticked.
2. Independently inspect Hubitat identity/capability and the validity of each requested time window BEFORE drafting and freezing. Tick the **operator target-check attestation**. The application does not independently perform target validation.
3. Prepare **4–10 truly new**, read-only, uncoached causal questions, ideally 6–10 covering at least three evidence domains such as lighting state transitions, independent controller/automation activity, heating-state changes, ventilation events, hub incident/reboot causation, and device/network state reports. Prefer events not previously shown to the model, developer or evaluator. Do not recycle any exposed `hold-..`, `sr-..`, `new-01/02`, or earlier event-specific benchmark from the project.
4. Vary the truth conditions: plausible direct command evidence, a state-only report where the initiator is unverified, competing actors, bounded/incomplete history, and genuinely unavailable discriminating source. Do not tell the model which evidence it should find. For instance, a normal first-answer question format is **Why did [verified device] change state at [verified event time]? Do not change anything.** The bracketed form is an illustrative template, not a frozen test question.
5. Click **Freeze new question set** exactly once. Save the private commitment and question set locally; the study is memory-only and vanishes on add-on restart. The SHA-256 commitment proves internal consistency of the submitted question bank, not independent timestamps or true first-attempt isolation.

## Run and assess each blinded pair

1. Select a frozen case. Explicitly consent to two model answers, access to private sources and—if using Ollama Cloud or another remote model—evidence transfer/credit usage.
2. Click **Run blinded read-only pair**. Baseline Agent and candidate SourceLedgerExperimentalAgent select their own allowed native MCP reads, in fresh contexts. Each arm sees independent live reads and may receive different state/history snapshots. First attempts cannot be retried.
3. Read A and B carefully and inspect every **private tool receipt**, particularly command issuance versus downstream device state reporting, timestamps, actor identities, filtered/truncated logs, automation source attribution, and competing hypotheses. Source absence does not prove an action never happened.
4. Inspect **Original source-response comparability**. A matching tool name and args is not an identical snapshot; identical normalized returned payloads are stronger but still not proof of full historical capture, physical causation or independent ground truth. When key reads differ or fail, mark any paired conclusion that relies on equal evidence as confounded.
5. For each answer, set **Evidence for distinguishing competing causes** to sufficient / partial / unavailable / not verified. Tick original-receipts-inspected and all-definite-cause-claims-reviewed only after actually completing that review.
6. In the claims text area, enter each distinct **definite causal assertion**, one per line, in the format `verdict | exact short claim | 0,2`. Verdict is `supported`, `unsupported` or `unverified`; receipt numbers are zero-based and refer to the displayed original tool receipts for that arm. A `supported` assertion must refer to at least one successful native read, though correct attribution still depends on human judgment. For claims with no supporting receipt use an empty final field, e.g. `unsupported | The named app sent the OFF command | `. Do not paste credentials.
7. If the answer explicitly and appropriately leaves causation unverified, **leave the definite-claim list empty**; this is not an automatic failure. Always score **causal_calibration** 0 / 1 / 2, **never n/a** for a causal-study question, taking into account uncertainty, coverage and contradictory/unavailable evidence. A full 2 is rejected if the same review identifies an unsupported definite cause.
8. Score factual grounding, source completeness and usefulness independently on 0–2. Save the two complete blind ratings and human evidence audits atomically. They become immutable. Keep the experimental allocation hidden until all cases are rated.
9. Download each **PRIVATE case JSON** to a secure local Windows folder before restarting; it contains household questions, original MCP receipts, model answers, and any quoted cause assertions. Do not commit raw case files or credentials.
10. When every pair is reviewed, download the **privacy-safe aggregate report**. It contains only per-condition scores, claim verdict counts, read-source parity counts, timing and error counts, and explicit NOT independently verified flags. Compare factual/causal outcomes, overconfident definite causes, source sufficiency, target validity, tool errors and latency. Never infer quality from model confidence or tool counts.

## What is or is not demonstrated

- **Engineering CI:** can validate the frozen/readonly gates, pure receipt comparison, claim-review schema and privacy/score invariants using fictional sources. It does not validate live model accuracy, matched time windows, hub retention, first-attempt truth or real-world causes.
- **Human review:** the user/evaluator manually states which cause claims are supported by which returned receipts. Tool receipt references are necessary but do not themselves prove independent causation.
- **Source parity:** automatically compares complete successful returned tool-call multisets; *same-call/different-payload* and unmatched tool calls must be noted as confounders. Exact matching is intentionally strict; result equivalence is not causal ground truth.
- **Zero unsupported cause claims:** meaningful only when the denominator of reviewed definite assertions and completeness of review are reported. An empty claim list may indicate justified restraint rather than failure.
- **Promotion:** no source-ledger or alternative generic reasoning intervention can be promoted from the already exposed cases or a single small exploratory causal set. Decide prospectively using source-reviewed, independently adjudicated outcomes. Preserve the model's natural tool selection rather than introducing fixed plans or incident-specific answer rewrites.

**Rollback:** Install a previous v2 release or ignore the new causal-mode reviewer. The production Agent, v1, read-only client permissions and external diagnostics recorder do not change when you use or remove the reviewer.
