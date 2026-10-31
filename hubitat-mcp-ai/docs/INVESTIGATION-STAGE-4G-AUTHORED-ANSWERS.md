# Stage 4G — Real model-authored investigation answers (offline, constructed)

Source version **v0.18.287**, based on merged v0.18.286.

## Why Stage 4G

Stage 4F tested reviewer **classifications**, not full answers. In its
actual local CPU Ollama run Qwen2.5 3B accepted all four supported
synthetic statements and rejected all four unsupported statements.
Llama 3.2 3B accepted three of four unsupported statements. Neither
result proves either model can actually *investigate* or write a useful
answer. A proof-of-publication switch is **not** justified.

Stage 4G therefore asks **Qwen2.5 3B to author complete natural-language
explanations** based on scoped synthetic source facts. Four independent
questions cover lighting, heating, ventilation and source/collector
history. The last case includes both an observed event and an explicit
historical coverage gap.

### Source-to-prose flow

1. The host selects a bounded, source-typed Stage 4A evidence packet;
   the author receives the user-style question and the packet.
2. A real locally downloaded model writes **its own** one or two
   complete sentences with explicit host-provided citation IDs.
3. A strict structured JSON schema limits only the output shape and
   valid fact-ID vocabulary; it does **not prewrite answer text** or
   select a causal conclusion.
4. The host validates cited IDs, directly projects each selected
   host-owned source fact into the Stage 4A typed claim envelope,
   and checks exact source-fact fidelity. **Those typed claims are
   derived by the host, not model-authored factual attestations.**
5. The unchanged authored sentence is separately submitted to
   Qwen2.5 3B and Llama 3.2 3B as Stage 4B reviewer requests. Each
   sees only its cited facts and its sentence, not an answer key or
   the other reviewer's response.
6. The host compares the set of facts cited by the candidate answer
   against the separately held expected source-fact IDs. These
   **coverage labels are never given to the model or reviewers**.

### What is and is not measured

The result counts actual author calls/responses, source-valid vs invalid
JSON proposals, citation coverage of five independently expected facts,
authored sentence/word totals, complete reviewer responses, agreements
and disagreements. Only bounded aggregate fields leave the runner.

**Important limitations:**
- Host-owned citation coverage is **not** a semantic entailment proof.
  A model can cite a correct command but falsely claim the boiler
  physically ignited. That sentence may pass the structural check.
- Both reviewers can accept a false cause. Qwen as both author and
  reviewer has correlated error risk, and Llama's Stage 4F false
  acceptance rate was high. Their agreement is **diagnostic only**.
- Model-generated sentences have **no independently adjudicated
  sentence-level oracle**. This run measures format, source selection,
  possible reviewer support and completeness, **not** actual hallucination
  rate or independently reviewed naturalness.
- Word totals do not prove clarity, usefulness or Claude-level quality.
  User-facing prose is intentionally not uploaded to a public GitHub
  log. Human editorial assessment of private generated prose would
  need a separate, deliberately authorised local review.
- The model receives only synthetic already collected evidence.
  It is not choosing new MCP reads, recovering real history,
  investigating automations, or controlling any Hubitat/HA device.
- There is **no publisher change or production rollout**.

## Running without a PC

The additive `.github/workflows/stage4g-authored-answer-evaluation.yml`
workflow runs on a temporary GitHub Actions CPU machine with local
Qwen2.5 3B and Llama 3.2 3B weights, `OLLAMA_NO_CLOUD=1`,
`OLLAMA_HOST=127.0.0.1:11434`, no secrets, no cloud inference,
no real household files or network addresses. It is triggered for
changes to its own workflow/runner/source and can be manually
dispatched later from GitHub Actions.

It records only aggregate metrics in the job summary and console,
no model-written sentences, exact source IDs, timestamps, prompts or
secrets. If all four author responses are invalid, the job ends
**INCONCLUSIVE**, never a fake 100% score.

## Acceptance gate

Merge Stage 4G source-only code **only** if all repository workflows
and the actual-model workflow succeed at the final PR head, and
inspect the measured source-fact coverage and reviewers' diagnostic
verdicts. A passing CI job alone cannot establish publication
safety.

Next: independently adjudicate real model-authored wording on a
larger privacy-safe reference corpus, measure unsupported causation
and omissions, compare different models and prompt variants under
matched conditions, and only then seek separate owner permission
for supervised live read-only observation.

No installed Home Assistant upgrade required, no Hubitat/HA change.
Rollback by reverting this source-only PR or disabling the workflow.
