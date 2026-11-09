# HomeBrainOS v2 — Next milestone: source-real first-answer acceptance

**Established:** 9 November 2026. **Implementation phase:** independent measurement groundwork; no change to production agent behavior. **Baseline:** v2 repository version 2.0.0-alpha.26, or exact version/SHA captured at deployment. Do not assume that a merged build is installed.

## Why this milestone exists

The frozen six-case fictional A/B evaluation was fully completed and unblinded. An extra generic investigation-completion prompt scored 36/50 vs 31/50 for unchanged baseline, but **causal calibration tied at 7/12** and the strict discriminating-source checks also tied at 10/23. Therefore the experimental prompt is **not promoted** and those six revealed scenarios cannot serve as fresh validation. These are small, ChatGPT-assisted human ratings, not independent accuracy estimates.

**Goal:** find the general source-selection and tool-schema obstacles that prevent a useful, verified answer the first time. The model remains responsible for selecting relevant live MCP reads, deciding when the evidence is sufficient and writing natural, cautious explanations. No hardcoded per-device tool plans, event-specific heuristics, fabricated source coverage or answer rewrites.

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
