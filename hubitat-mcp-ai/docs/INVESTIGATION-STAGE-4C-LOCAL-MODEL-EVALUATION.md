# Stage 4C — Real local-model semantic evaluation, without live publication

Version **0.18.283**; baseline **0.18.282** (Stage 4B).

## What changed

Stage 4B defined a two-reviewer entailment contract and benchmark, but its
review votes were **constructed**, not returned by a real language model.
Stage 4C adds an *executable offline inference runner*. It can invoke two
distinct locally installed Ollama models and, optionally, a third authoring
model, over synthetic or manually reviewed offline evidence.

Stage 4C is **not imported** by the running HomeBrain agent, its installed
add-on factory, final answer coordinator or V3 publisher. It makes zero
Hubitat, Home Assistant or MCP requests, and it never controls devices.

## Running locally (optional, deliberate operation)

Using a trusted offline machine with an already installed and running local
Ollama service and two different **locally resident** models:

```bash
cd hubitat-mcp-ai
python tools/stage4c_local_model_eval.py \
    --demo-constructed \
    --reviewer-1 qwen3.5:4b \
    --reviewer-2 llama3.2:3b \
    --enable-local-inference \
    --ack-local-data-processing
```

This mode uses eight constructed reference sentences from four domains,
with independently authored reference labels. The **two model reviewers
are actually invoked**, unlike Stage 4B's static reviewer results. Its
false-accept and false-reject metrics become meaningful only for these
constructed test statements and **not** as proof of performance on genuine
home incidents.

To ask a *third* local model to author genuinely new natural-language
explanations (which are then reviewed by the other two models):

```bash
python tools/stage4c_local_model_eval.py \
    --demo-constructed --generate-drafts \
    --author qwen3.5:4b \
    --reviewer-1 llama3.2:3b \
    --reviewer-2 qwen2.5:3b \
    --enable-local-inference \
    --ack-local-data-processing
```

The three model tags must be distinct. Each must already be available
locally in Ollama; **no models are downloaded automatically**. The runner
does not activate HomeBrain or query Hubitat/HA.

For owner-supplied offline cases, provide a private JSON file with a single
`cases` root array. A case has an allowlisted `domain`, a short safe
`case_id`, `trace_origin` of `constructed-fixture` or
`owner-labelled-redacted`, a Stage 4A source `packet`, and either a
typed-valid Stage 4A `draft` with *independently authored* per-sentence
`oracle` labels, or no draft for on-demand generation. Maximum eight cases
per run, max 16 sentences per draft, max 80 cited packet facts, and max 24
model invocations across one run. Input file max 512 KiB.

Use:

```bash
python tools/stage4c_local_model_eval.py \
    --input /private/review-cases.json \
    --reviewer-1 qwen3.5:4b --reviewer-2 llama3.2:3b \
    --enable-local-inference --ack-local-data-processing
```

## Security boundaries

- **Two explicit CLI flags** are required before reading a private file
  or initiating a request.
- HTTP is fixed to `127.0.0.1:11434/api/chat` (optional local port).
  Proxy environment settings are ignored; all HTTP redirects are blocked.
  Local request/read timeout <=120 seconds, output <=32 KiB and prompts
  <=96 KiB. No API keys, external URL selection or cloud model tags.
- Verify your Ollama service actually uses **local inference**: local
  loopback HTTP alone cannot prove a local model is not backed by a remote
  cloud service. The model identifier must not contain `cloud`, and the
  host administrator must confirm model storage/compute location.
- The runner sends a sentence and **only its cited host evidence** to
  each reviewer. It does not send reference labels, prior reviewer votes,
  other reviewer responses, causal conclusions or model-generated prose
  from unrelated cases. Both reviewers receive identical content but are
  invoked separately.
- The local CLI never prints input case contents, exact IDs, event clocks,
  prompts, model outputs, model names or exception text. It prints only
  allowlisted aggregate statistics. No output file or new background job
  is created. Keep private input files on your trusted local machine.
- This code cannot verify **actual statistical independence** of the two
  reviewer models; separate identifiers and separate calls are not enough
  to claim independence.
- **Generated drafts cannot reuse benchmark truth labels.** A fresh
  model-authored sentence needs *new, independent, sentence-specific*
  expert adjudication after generation. It is reported as **unscored**,
  even when both reviewers agree it is entailed.
- If reviews fail, time out, disagree, or are malformed, they do not count
  as successful reference scores. A complete, adjudicated reference case
  is scored for false acceptance and false rejection through Stage 4B.

## Evidence and claim limitations

Semantic entailment reviews are fallible. A supported native command does
not establish physical response or upstream decision. Source timestamps
and collector reception timestamps differ. Truncated, missing, or empty
history cannot support claims of command/event absence. Agreement of two
bad reviews can create a false acceptance, which independent reference
judgments and adversarial testing must expose.

**No model-generated prose is approved for production** by this runner.
The return report always has `safe_to_publish=false`,
`semantic_ground_truth_independently_verified=false`, and
`production_model_or_publisher_changed=false`.

The local script and source module do not prove that actual models were
run in GitHub Actions; CI uses fake in-process adapters plus a mocked
local transport. **No genuine inference was performed as part of this PR.**

## Next acceptance gates

1. On a trusted machine, voluntarily run the opt-in local evaluation
   against two genuinely separate installed models; collect **aggregate
   counts only**, not raw household event logs.
2. Expand the independently adjudicated reference corpus across lighting,
   heating, ventilation, power and offline/stale-device investigations.
3. For model-generated sentences, obtain separate expert labels *after*
   generation and independently rerun validation before computing
   accuracy. Compare both false acceptance and unnecessary rejection.
4. Verify model transport, clock/issuer errors, completeness of reasoning,
   usefulness of next-read suggestions and realistic latency.
5. Only after adequate field data and **separate owner approval**, propose
   a reversible production shadow comparator. Do not switch over the
   live publisher or authorize additional device controls.

Source rollback: revert this additive PR. No installed add-on settings,
model calls, device state or user data need migration.
