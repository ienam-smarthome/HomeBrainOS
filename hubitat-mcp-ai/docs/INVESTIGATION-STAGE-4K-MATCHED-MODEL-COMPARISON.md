# Stage 4K — Matched 3B-versus-7B extraction comparison

**Source-only:** 0.18.291, based on merged 0.18.290.

## Hypothesis and controlled experiment

Stage 4J's actual local `qwen2.5:3b` semantic extractor completed
12/12 structured responses but correctly extracted only 8/15
host-curated atomic propositions, missed 2/6 independently labelled
high-risk claims, and produced 29 extra labels (precision 21.62%,
recall 53.33%). This is not production-grade semantic coverage.

Stage 4K tests whether a larger same-family model improves these
errors **without changing** the prompt, schema, sampling temperature,
source packets, proof checker or reference labels.

A single isolated GitHub-hosted CPU runner downloads both locally
resident `qwen2.5:3b` and `qwen2.5:7b`. For each model it executes:
1. The exact 12 original Stage 4J constructed sentences.
2. A separate **8-case held-out synthetic set**, newly pre-annotated
   and not included in previous Stage 4J actual-model runs.

This is 20 cases × 2 models = **40 actual local inference calls**.
Both models receive the same `_SYSTEM` instructions, Stage 4J
per-proposition JSON grammar, options `temperature=0` and
`num_predict=768`, and source scopes. The only intended variable
is the Ollama model tag. The 3B and 7B sizes and their exact
availability were confirmed in Ollama's public model catalogue.

Per model **and per corpus**, measure structured response validity,
exact atom matches, precision, recall, missed high-risk implications,
extra atoms, host source-proven/unproven assertions, and invocation
errors. Model-to-model differences are calculated after independent
host reference scoring, never from model confidence.

## Held-out cases

The eight new constructed sentences include a combined valid lighting
command and invented physical lamp illumination; source-recorded
issuer; heating command paired with an explicit unverified physical
response; a claim that radiators heated; fan OFF plus invented motor
stop; contact collector timestamp paired with incomplete history;
a true archive gap misinterpreted as proving no other events; and
an unverified causal relationship between a contact observation
and an archive gap. Reference atom labels are withheld from models.

This is a **controlled model-size comparison on synthetic examples**.
The eight holdout labels are host-curated and were not independently
adjudicated by humans. The experiment does **not** grade the exact
newly model-authored Stage 4G answers or prove completeness on unseen
free-form prose. A higher 7B recall may come at worse precision,
so *both* metrics and high-risk misses must be reported.

## Ollama Cloud production distinction

**The owner's HomeBrainOS uses Ollama Cloud online models for AI
reasoning**, alongside a separately hosted/local Ollama fallback.
This benchmark is deliberately **NOT** an Ollama Cloud model test:
it invokes locally installed Qwen2.5 3B and Qwen2.5 7B weights
on an ephemeral GitHub runner. The local models may differ substantially
from the live online model and provider-side inference settings.

No cloud account, tokens, paid inference credits or private house
data are used in Stage 4K. **Passing or failing this test is not
grounds to select, replace, disable or certify the owner's
actual cloud model or live HomeBrain routing.** The next stage
should inspect the currently configured Ollama Cloud model and
evaluate it with approved synthetic requests under separately
authorised credentials/connector access, using the same evidence
reference standards. Do not assume a previously tried model tag
is still the current live choice.

## Privacy, cost and operational boundaries

The runner uses public local model weights and **no cloud inference**:
`OLLAMA_NO_CLOUD=1`, `OLLAMA_HOST=127.0.0.1:11434`,
`OLLAMA_MAX_LOADED_MODELS=1`, read-only GitHub permissions,
no credentials or user files, and source-only synthetic evidence.
No Hubitat, HA, MCP, household address, live source history or
installed add-on connection. The workflow limits CPU execution,
uses no recurring schedule, does not upload artifacts, and logs
only bounded aggregate metrics and approved model names.
If the run fails or some model arm has no valid responses, it must
be labelled **INCONCLUSIVE**, not reported as zero false accepts.

The original Stage 4J 3B-only workflow and reference results remain
available unchanged; the Stage 4K workflow is separate and additive.

**The actual current publisher and local/paid model routing remain
untouched.** The Stage 4J host proof checker does not certify
that all free-text implications have been extracted. Even perfect
accuracy on 20 synthetic sentences is not permission to publish.
The comparison result always declares
`publisher_approval=false` and
`comparison_of_created_answers=false`.

## Acceptance

Run all three standard repository workflows and the separate real
3B-versus-7B GitHub Action at the exact final PR head. Record
validated scores, explicitly highlight safety regressions,
and merge only the isolated comparison if all code/inference
checks are green. Do not substitute mocked unit-test outputs
for real model results.

Next, before any supervised production shadow, introduce a secure,
opt-in, **independent post-generation human annotation route for
genuinely model-authored answers**, collect a larger representative
reference corpus and audit whether textual implications are
exhaustively captured.

Rollback: revert additive Stage 4K source and/or disable its
standalone workflow. No installed add-on update required.
