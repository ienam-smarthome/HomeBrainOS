# HomeBrainOS v2 — Next milestone: source-real first-answer acceptance

## 10 November 2026 — Alpha.35 next checkpoint: independent first-answer transfer tests

**Current code baseline:** `2.0.0-alpha.35` on GitHub `main`, merge `68729a1c` after PRs #1577/#1578, with green main-branch CI. Installed Home Assistant version is not established from a repository merge. The previously tested household incidents and frozen synthetic holdouts are **exposed**, not unseen evidence for an unbiased improvement claim.

**Objective:** distinguish `can retrieve data` from `can decide which data proves an event-specific cause`. The next practical milestone is a short, diverse, **uncoached live first-answer series** rather than modifying the agent for one device, timer or chart.

### Proposed cross-domain new-turn trials

Use privately selected devices and recent incidents in the installed UI; the themes below deliberately contain no household identifiers or actual source data.

1. **Historical switch/control investigation:** most recent switch OFF; separate explicit `off()` command issuer, device/bridge state reporter, controller settings, and the internal condition that initiated the command; check alternative configured OFF paths.
2. **Power-versus-state discrimination:** investigate a low/zero-power reading and whether a physical supply loss is established. Correlate switch, voltage and historic meter events instead of equating 0 W with OFF.
3. **Historical heating coherence:** compare a room valve's heating state to the main heating demand **at the same historical moment**, including participating zones and coordinator settings. Current idle readings cannot prove a historical no-demand condition.
4. **Independent telemetry-source comparison:** compare an external probe and native five-minute samples by **original timestamps, source basis and lookback**; a graph correlation does not prove a reboot or root cause.
5. **Positive-control incident:** when explicit triggering event, controller execution trace and resulting state are all actually returned and temporally compatible, test whether the model correctly says that cause is verified rather than hiding behind generic uncertainty.

Each question should end in **"Do not change anything."** Start a new Ask conversation, copy the unedited first response and original private Technical JSON, and review outside the repository. If installed version differs from the target or a call failed, record it; do not silently switch test conditions or rerun as though it were the first attempt.

### Acceptance dimensions

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Factual grounding | Contradicts/creates source facts | Mostly correct but material error or omission | All material factual claims match retrieved original successful receipts |
| Source completeness | Misses essential discriminating source class | Relevant reads, significant coverage caveats unresolved | Proportionate relevant reads and accurate explicit scope; no invented complete history |
| Causal calibration | Unsupported definite cause or contradicts temporal record | Properly qualified but significant logical/source weakness | Event-specific cause supported, or uncertainty correctly tied to named missing evidence |
| Usefulness | No actionable/evaluable answer | Partial but useful | Direct, concise answer plus appropriately bounded evidence |

`n/a` is allowed only where a dimension is genuinely inapplicable, not when a causal question is answered with "unknown." Distinguish *successful native receipt* from *true-world verification*. Record tool errors, source window, return limits, reporter versus actor, settings freshness and chronology separately.

**Change policy:** No production changes simply because one answer is partial or a known question was coached. Group independent new failures by general source-coverage, sequence-comparison, tool-schema or causal-assertion category. Fix at a general abstraction boundary only when observed across domains; ensure native tool autonomy, privacy, permission/confirmation checks and non-incident-specific regression tests remain intact. Keep a positive-control test to guard against excessive abstention.


**Established:** 9 November 2026. **Implementation phase:** independent measurement groundwork; no change to production agent behavior. **Baseline:** v2 repository version 2.0.0-alpha.26, or exact version/SHA captured at deployment. Do not assume that a merged build is installed.

## 10 November 2026 — Live-first development replaces mandatory A/B workflow (alpha.29)

User-directed switch: normal **Ask / Chat** is the primary live testing and day-to-day surface. **Copy for review** copies unmodified Technical JSON with a neutral evaluation request, allowing receipt-backed informal scoring without freezing a new blind A/B bank. Older experiments remain available under **Experiments (optional)**; no study data is deleted. Native Agent/tool/permission/confirmation behavior, Hub Diagnostics and installed hub settings are unchanged. Case scores are **not** independent blinded accuracy statistics. See [live review guide](HUBITAT-MCP-AI-V2-LIVE-REVIEW-WORKFLOW.md). The alpha.28 causal A/B process below is optional, not a gate for everyday UX work.

## 10 November 2026 — Historical optional gate: alpha.28 causal evidence audit

The two newly frozen alpha.27 real-source pilot pairs are now complete. Their experimental collection-ledger candidate was **not promoted** (lower factual-grounding and source-completeness scores; causal calibration not applicable). The upcoming alpha.28 opt-in evaluation adds private claim-by-claim causal review and strict comparison of original source read receipts, **without changing model-led production behavior**. Plan a fresh, cross-domain, read-only causality study with independently checked target/capability/time details, human evidence review, and explicit unanswered-source treatment. Do not reuse the exposed alpha.27 pairs, source-real ten-case captures or older fictional holdouts for independent validation. See [alpha.28 study runbook](HUBITAT-MCP-AI-V2-CAUSAL-REVIEW-READINESS.md) and [alpha.27 pilot result](HUBITAT-MCP-AI-V2-SOURCE-LEDGER-PILOT-RESULTS.md). This update supersedes the earlier "not yet captured" phase descriptions below, which are retained as historical milestone notes.

## Why this milestone exists

The frozen six-case fictional A/B evaluation was fully completed and unblinded. An extra generic investigation-completion prompt scored 36/50 vs 31/50 for unchanged baseline, but **causal calibration tied at 7/12** and the strict discriminating-source checks also tied at 10/23. Therefore the experimental prompt is **not promoted** and those six revealed scenarios cannot serve as fresh validation. These are small, ChatGPT-assisted human ratings, not independent accuracy estimates.

**Goal:** find the general source-selection and tool-schema obstacles that prevent a useful, verified answer the first time. The model remains responsible for selecting relevant live MCP reads, deciding when the evidence is sufficient and writing natural, cautious explanations. No hardcoded per-device tool plans, event-specific heuristics, fabricated source coverage or answer rewrites.

## 9 November 2026 — Phase 2: frozen source-real capture pack prepared

A new **offline-only** `hubitat-mcp-ai-v2/tools/source_real_acceptance.py` utility prepares a private, SHA-256-sealed bank of ten new read-only questions using user-supplied device/app labels and verifies the unchanged first Technical JSON exported for each. The fixed categories differ from the six revealed fictional `hold-..` tests. It detects question mismatches, duplicate request identities, self-reported prior conversation evidence, command attempts, incomplete capture, inconsistent installed version and model fingerprints. It reuses the private reviewer audit from Phase 1; it never calls a model, MCP, HA or a device and does not export original question text or receipts. It cannot prove a real source or first attempt without the operator's attestation. A human-reviewed score is permitted only for a fully captured pack without reported prior-source carryover or a device-command attempt.

See [private capture instructions](HUBITAT-MCP-AI-V2-SOURCE-REAL-CAPTURE.md). **No actual new real-hub observations are supplied yet**; first-answer factual and causal quality remain `not_measured`. A **server-enforced read-only token** is required before any source-real collection through the installed Ask UI. The production model/tool loop is not changed, and the generic synthetic prompt candidate remains unpromoted.

## 9 November 2026 — Phase 3: First ten source-real receipts supplied, preliminary review

Ten new source-real Ask Technical JSON captures were supplied for `sr-01` through `sr-10`, all reporting the same installed alpha.26 and cloud model, ten distinct request identities, **21 native tool attempts / 20 successes / one server-side error**, 29 rounds and no device-control calls. The local frozen-question manifest/seal was **not** included in the attachments, and a read-only info response reported `writeEnabled: true`; source-real origin, first-attempt isolation and actual server-token read-only permission have **not been independently proven**. Treat these as useful *real-source receipts* but do **not** label the study fully integrity-verified.

The receipt-bounded preliminary classifications were: four source-supported, four partial/qualified (including a motion sensor accidentally used as a contact test target), and two material errors. Mechanisms include wrong aggregation of returned values, bounded history assumed complete, truncated/filtered logs presented as wider coverage, a related app mistaken for the exact named target, and command/reboot intention conflated with verified effect. See [privacy-preserving case findings](HUBITAT-MCP-AI-V2-SOURCE-REAL-RESULTS.md).

**Consequence:** These ten tests are now observed and cannot be a new unseen acceptance set for a candidate trained on their findings. Preserve the original answers. Do not promote the synthetic candidate or alter production behavior based on this single, assistant-informed provisional review. Next require the **original private manifest + SHA seal**, independent source/permission verification, then a prospective A/B study on a **newly frozen** case bank with causal calibration as the primary outcome.

## Scope and sequence

1. **Review-grade capture (implemented in this phase):** Reuse the existing private first-answer Technical JSON auditor, which reports source-window limitations, tool schema rejections, tool calls, elapsed time and command evidence. An optional **separate human-review JSON** attaches claim-level factual grounding, definite unsupported causal claims, usefulness and sufficient-source assessments to the same privately ordered exports. Quality never becomes measured merely because MCP reads succeeded.
2. **Unseen source-real sample (not yet collected):** Select a frozen, previously untested set of ordinary first-attempt questions across status, lighting, device history, heating, humidity, connectivity, automation/commands and evidence-unavailable requests. Prefer a read-only upstream token and the same configured model. Preserve the exact question and full v2 Technical JSON privately; record installed build/model/provider, date, source permissions and any missing source classes. Use the same uncoached question once per subject. Do not run writes for evaluation.
3. **Independent review (not yet performed):** A human checks actual source receipts against every consequential factual/causal conclusion, missing relevant reads, historical coverage, group membership and user usefulness. Unsupported definite causes are counted by claim, not inferred from phrases. Where source records cannot be inspected, mark unverified; do not score missing data as correct. Prefer a reviewer who has not seen the candidate allocation.
4. **Mechanism diagnosis (after results):** Partition errors into: wrong/invalid tool arguments, unavailable source, failure to seek a discriminating read, erroneous interpretation of available source, unsupported causal certainty, and ineffective final explanation. Track first-attempt correctness and latency separately; do not translate tool count directly into answer quality.
5. **Prospective model-led intervention (future phase):** Only if independent new evidence supports it, test one *general* fix to MCP schema comprehension or evidence-sufficiency decisions against unchanged production, using **another new frozen** set. Model retains tool choice and natural language; schema authority and permissions stay upstream. If no significant causal improvement, reject or revise the hypothesis rather than patching these evaluated incidents.

## Private manual-review overlay: opt-in, no credentials

Existing CLI (no model, hub, network or HA calls):

```powershell
python hubitat-mcp-ai-v2/tools/first_answer_audit.py case01.json case02.json --output first-answer-summary.json
```

Until human reviews are attached, `quality_status` remains `not_measured` and grounding/usefulness/causal scores remain null.

Create a private `source-real-reviews.json` **locally**, in the same positional order as the Technical JSON files supplied to the CLI:

```json
{
  "schema": "homebrain-v2-source-real-human-review.v1",
  "reviews": [
    {
      "export_index": 0,
      "first_attempt": true,
      "source_kind": "real",
      "factual_claims_reviewed": 5,
      "supported_factual_claims": 4,
      "definitive_causal_claims_reviewed": 1,
      "unsupported_definitive_causal_claims": 0,
      "useful_first_answer": true,
      "relevant_sources_sufficient": false
    }
  ]
}
```

The numbers above are **illustrative schema values, not real HomeBrain evaluation results**. `export_index` is zero-based and refers to the position of a private export passed on the command line. Review records are optional for any unreviewed export; each position can be scored at most once. If the first attempt cannot be attested, use `first_attempt: false`. If the packet is fictional, use `source_kind: "synthetic"`; if origin is unknown use `"unknown"`. Non-real and non-first-attempt rows are **excluded** from source-real first-answer quality denominators. For `useful_first_answer` and `relevant_sources_sufficient`, use `null` rather than guess when undetermined.

Apply the human review without exporting the private answers or receipts:

```powershell
python hubitat-mcp-ai-v2/tools/first_answer_audit.py case01.json case02.json --reviews source-real-reviews.json --output reviewed-summary.json
```

The output contains descriptive score denominators, counts and anonymised receipt metadata. `quality_status` is `human_attested_partial` or `human_attested_complete` only where qualifying reviews are supplied; an empty or inapplicable review set remains `not_measured`. `grounded_claim_rate` is null if no factual claims were reviewed. The unsupported definite-cause count is null if no definite causal claims were reviewed, so a zero-denominator case never masquerades as zero unsupported causes. The tool **does not independently prove** source provenance, freshness, reviewer independence or factual correctness; those remain human attestations.

**Privacy boundary:** Keep original Technical JSON exports and private reviews outside the public repository. No raw question, answer, event row, tool argument, model label, private note, room identity or review filename is copied into the aggregate. The published script is runnable offline and never fetches source data.

## Acceptance and stopping conditions

- Capture real first-attempt denominators and source origin; do not mix the six old fictional holdouts into an unseen real sample.
- Human-review all material factual conclusions and definite cause claims; **target ≥90% grounding and zero unsupported definite causes**, with numerator/denominator reported rather than presumed.
- Target **≥80% useful first answers** across a sufficiently varied set, report insufficient relevant reads and contract errors independently.
- Compare actual model/provider, tool schema, complete source evidence, inference rounds, request latency and operator permissions fairly. Do not promote a prompt or generic engine mechanism based on synthetic CI passing.
- No automatic device control, permission bypass, native Rule Machine edits, Home Assistant changes or cloud spending occurs through this audit tooling.

**Release/integration:** This phase changes only the *offline acceptance audit* and tests/docs. Production v2 model guidance, tool loop, Hub Diagnostics, v1 and the previous blinded study remain unchanged. A later code or model intervention must have its own PR and prospective source-real evaluation.
