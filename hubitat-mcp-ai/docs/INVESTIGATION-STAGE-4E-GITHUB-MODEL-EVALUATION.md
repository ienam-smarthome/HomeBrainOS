# Stage 4E — Actual small-model reviews on GitHub Actions

**Source version:** 0.18.285; base v0.18.284.

## What is genuinely executed

The new `.github/workflows/stage4e-actual-model-evaluation.yml`
workflow starts an **ephemeral GitHub-hosted CPU-only runner**, installs
official Ollama, downloads the locally resident model weights
`qwen2.5:0.5b` and `llama3.2:1b`, and invokes their **actual** model
responses via the already merged Stage 4C localhost-only adapter.

There are **eight constructed, independently labelled test sentences**
(lighting/heating/ventilation/history, four supported and four unsupported).
Both models are asked separately to review each sentence, for **16 local
model invocations**. They receive source evidence and authored text but
**never the reference answer, another reviewer response or any live Home
Assistant/Hubitat material**. The runner verifies it attempted 16 calls.
The completed review envelopes are measured with Stage 4B's existing
independent-reference benchmark. Unparsed/invalid responses count as
incomplete; they are **not** silently scored as mistakes, success, or
0%-false-accept rates.

This is a real-model **semantic reviewer** evaluation. It is **not yet**
a live HomeBrain incident evaluation, does not run a third authoring
model, and cannot establish human-level/Claude-like accuracy. The tiny
CPU-oriented models test feasibility of the evaluation path and may be
weak at exact structured JSON. Distinct model tags are not independent
truth or independent source attestations.

## Privacy and security

- No household data, authentication tokens, local network addresses,
  HA/Hubitat tools, new app endpoints, automations or uploads.
- Repo permissions limited to `contents: read`; checkout does not
  persist credentials; no secrets are passed to the runner.
- The workflow is PR-triggered **only when its own code or supporting
  Stage 4 files change**, and blocks external forks. A manual
  `workflow_dispatch` trigger is also defined for later reruns.
- Ollama binds only `127.0.0.1:11434` and has
  `OLLAMA_NO_CLOUD=1`. The two exact model tags are publicly available,
  small local models. Internet is needed only to install Ollama and
  download public weights, not to upload prompts.
- The Python evaluation script refuses execution outside GitHub Actions,
  or without an explicit synthetic-only flag and local/no-cloud
  environment. Inference uses the existing Stage 4C adapter, which
  blocks proxies, HTTP redirects and cloud model names.
- The public GitHub Actions step summary and console print
  **aggregate counts only**: calls attempted, valid paired reviews,
  false accepts/rejections, incomplete reviews, and N/A when no
  scores exist. No raw prompts, model responses, individual cases,
  device IDs, timestamps or source names are uploaded or logged.
- A complete pair requires schema-validated model output; if there are
  zero complete pairs the job exits **INCONCLUSIVE** (non-success),
  rather than announcing a fictitious accuracy improvement.
- Bounded run: 40-minute job timeout, 27-minute inference step,
  90-second per-call timeout, 8 cases and 16 calls. No scheduled
  recurring model downloads or ongoing paid services.
- `OLLAMA_NO_CLOUD` is a documented upstream Ollama setting. In this
  ephemeral environment, both model weights are pulled before
  local inference; no account or cloud API keys are supplied.

## How to review the results from a phone

Open the repository's GitHub **Actions** tab and find the workflow named
**Stage 4E actual small-model evaluation (synthetic only)**. Select the
latest run for PR #1173 (the stage-specific PR). The "Run summary" shows
the actual model-request counts and errors. Treat this as a measurement
of two small models on constructed source examples, not an evaluation
of your production HomeBrain instance.

If GitHub's policy requires an owner to approve newly introduced
workflows, approval may be required in the PR checks UI. Do not bypass
that policy by using privileged `pull_request_target` events.

## Gates

1. All existing GitHub validation, full Python suite, smoke checks and
   the new actual-model job must run at the final PR head. CI tests of
   the *runner code* use fake model responses, but the dedicated
   GitHub workflow is explicitly intended to execute genuine weights.
2. Inspect **actual** results; do not infer model accuracy if the
   workflow is blocked, times out, downloads fail or responses are
   invalid. Differentiate operational failure from model quality.
3. Expand real-model benchmarks and post-generation, independently
   adjudicated answers before touching the production publisher.
4. Any opt-in live read-only HomeBrain evaluation or new publisher
   remains separately gated by the owner's approval and rollback.
5. No installed add-on upgrade is required to run GitHub-hosted tests.

**Rollback:** revert this source-only PR or disable this one workflow.
No live home state changed.
