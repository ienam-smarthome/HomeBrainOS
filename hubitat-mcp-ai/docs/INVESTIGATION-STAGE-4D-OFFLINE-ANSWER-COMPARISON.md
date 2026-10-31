# Stage 4D — Offline comparison of existing and model-authored answers

Source-only milestone **v0.18.284**, based on merged v0.18.283.

## Why this is not yet a production publisher change

Stage 4C provides an explicitly launched, local Ollama evaluation runner.
It can generate new answers and obtain reviewer votes, but the author
and reviewer models have **not been run in our CI**. Running the source
without a local model does not prove real model quality. The production
V3 publisher still contains bathroom-specific narrative rendering.

Stage 4D adds a different, equally important layer: compare an **existing
HomeBrain answer** with a candidate model-authored **Stage 4A JSON draft**
against the *same* evidence packet, without publishing either candidate
or modifying the existing response.

`stage4_offline_answer_comparison.compare_stage4d_offline_answers(cases)`
is a pure Python, memory-only function. It does not make a model call,
change the model's choice, collect live traces, dispatch an MCP call,
change a device, publish an answer, or persist source records.

## Three strictly separated signals

1. **Typed fact validity:** Reuse the Stage 4A host-source validator.
   A citation to an actual command does not prove its initiator or
   physical outcome.
2. **Semantic review concordance:** Reuse the Stage 4B dual-reviewer
   envelope checks. Agreements and disagreements are counts, **not**
   independent semantic ground truth. Reviewer envelopes must be
   supplied; missing or malformed responses are not scored as positives.
3. **Paired quality judgments:** Separately supplied, *post-hoc*
   evaluations of the baseline versus the candidate in five
   domain-general dimensions:
   `factual_fidelity`, `question_coverage`, `causal_calibration`,
   `clarity`, and `actionability`. Each must be one of
   `candidate`, `baseline`, `tie`, or `unresolved`. Cases
   with no judgment remain **unscored**, never treated as candidate wins.

Do not use model review votes as these paired labels. Labels should be
written **after both actual answer texts exist**, by a reviewer who
checks the separately scoped source record. This source-only harness
cannot authenticate who wrote the judgments, blind the adjudicator,
or establish that a genuine HomeBrain incident was tested. The report
always says this explicitly.

No hardcoded lighting, bathroom, humidity or particular automation
strings determine answer preference. There is no deterministic
word-routing or guessed causal explanation.

## Private input contract

Keep your data on a trusted local machine. A JSON input has a single
root `cases` array containing 1–12 entries. Each case contains:

- `case_id`: a short non-personal identifier such as `test-light-01`
- `domain`: one of the allowlisted Stage 4B domain categories
- `trace_origin`: `constructed-fixture` or
  `owner-labelled-redacted`; neither label is proof of provenance
- `baseline_answer`: the exact existing answer to compare
- `candidate_draft`: the exact Stage 4A model-authored JSON answer
- `packet`: the same bounded, host-issued Stage 4A source packet
- `reviewer_envelopes` (optional): two completed Stage 4B reviewer
  envelopes from the same candidate and evidence packet
- `pair_assessment` (optional): post-hoc quality judgments with
  `origin` (either `constructed-reference` or
  `owner-labelled-offline`) and `ratings` mapping **all five**
  named dimensions to one of the four comparison labels

Do not try to synthesize a false source packet from the current
answer's prose. A model-written draft needs its own source references.
The existing answer does not have Stage 4A fact IDs, so a side-by-side
quality rating is still a **supplied judgment**, not a machine proof
that either answer is source-grounded. Missing history remains missing
and cannot establish command absence.

Input is capped at 512 KiB, 12 pairs, 80 Stage 4A facts per packet and
12,000 characters of baseline text per answer. Over-limit data is
rejected, not partially represented as complete.

## Optional local CLI (no model calls)

```bash
cd hubitat-mcp-ai
python tools/stage4d_local_answer_compare.py \
  --input /private/paired-answers.json \
  --ack-private-offline-input
```

The CLI requires consent *before opening* the private input and prints
only a strict allowlist of **aggregate counts** and per-dimension
preferences. It does not print original answer prose, model responses,
case IDs, household names, source data, timestamps, app/device IDs, file
paths or exception contents. No file, upload or network call is made.

To produce actual semantic model votes separately, run the already
merged Stage 4C local Ollama CLI on an appropriate host:

```bash
python tools/stage4c_local_model_eval.py \
  --demo-constructed \
  --reviewer-1 qwen3.5:4b \
  --reviewer-2 llama3.2:3b \
  --enable-local-inference \
  --ack-local-data-processing
```

You must independently confirm the models are installed locally and
Ollama is not forwarding inference to a cloud model. This Stage 4C
command returns **aggregate scores only**. It does not export the raw
candidate/review data needed by Stage 4D. A future explicitly approved
local-only flow may provide a consented private transfer between stages;
do not circumvent privacy protections by copying real household logs or
tokens into GitHub, an issue, or a chat.

## Safety, validation, next stage

- Full CI and cross-domain synthetic regression are required before
  merge. These tests do **not** demonstrate genuine live model quality.
- The Stage 4D comparison returns
  `publisher_replacement_authorised=false`,
  `winner_selected=false`,
  `model_answer_semantically_proven=false` and
  `production_answer_changed=false` unconditionally.
- Existing V3/legacy answers, control commands, device permissions,
  active publisher and Stage 3F default-off capture stay unchanged.
- To compare real responses, obtain explicit owner consent to use
  redacted read-only source evidence on an isolated local host; validate
  fresh model drafts and obtain separately authenticated, blinded
  reference adjudication before calculating field-quality differences.
- Only after evidence of consistent usefulness and low false acceptance
  may a **separately approved** opt-in production shadow comparison be
  considered, followed by a reversible publisher rollout if justified.

Rollback: revert this additive PR. No live configuration or data migration
is involved.
