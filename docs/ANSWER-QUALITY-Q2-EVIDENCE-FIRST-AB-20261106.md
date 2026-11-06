# Q2 general evidence-first prompt A/B — unchanged source, no claimed accuracy score

**Date:** 6 November 2026. **Candidate type:** offline local model prompt experiment.
**Production:** unchanged; HomeBrainOS 0.18.427 remains the installed-version
reference, not proof of current installation.

## Hypothesis and pre-registered evaluation

Four prior user-provided first-answer pairs showed that smaller local models
can confuse recorded commands with physical execution, substitute mechanisms
for evidence, omit important source facts, and overlook missing source
identity. A **general evidence-first instruction** may improve causal
calibration and completeness without replacing the model's natural final prose
with canned incident-specific templates.

Baseline: the exact, original model-neutral `render_comparison_prompt(case_id)`.
Candidate: one general, domain-independent `render_evidence_first_prompt`
instruction. The **case ID, packet hash, question, evidence lines and final
model-output instruction are byte-identical** between arms, verified in
tests for every one of the 40 pre-existing frozen packets. Private human
rubric obligations are never included in either prompt. The original baseline
renderer and private Q2 local/Cloud capture defaults are unchanged.

The candidate encourages the model to distinguish a source report,
configuration, requested command, inferred relationship, and proven physical
outcome; time ordering alone from causation; and incomplete observations from
global absence. It asks for an accessible, concise explanation and a single
read-only follow-up if unresolved, not an output form, role-specific canned
answer or hidden evidence.

## Actual isolated model experiment

Workflow: `.github/workflows/q2-local-frozen-answers.yml`, now exercising
`hubitat-mcp-ai/tools/q2_evidence_first_ab.py` on same-repo PRs. The local
runner uses two **tiny engineering calibration models**, `qwen2.5:0.5b` and
`llama3.2:1b`, against the unchanged four reference cases for causal OFF,
heating restoration, MQTT freshness and native class identity.

- Each case/model receives **one** baseline and **one** evidence-first
  request, with frozen source and fixed `temperature=0, seed=7,
  num_ctx=4096, num_predict=320`. Sixteen first prompt-arm requests
  across eight matched model/source pairs. No model retries.
- Request order is alternated across model and case to mitigate cold/warm
  bias; one run cannot eliminate order effects or establish median/p95
  production latency.
- Ollama is restricted to `127.0.0.1:11434`,
  `OLLAMA_NO_CLOUD=1`, no MCP tools, no Hubitat/HA/router access,
  no API keys, no paid Cloud inference or production publisher.
  GitHub runner minutes may have an unmeasured infrastructure cost.
- CI emits only answer SHA-256, character lengths, prompt/source fingerprints,
  timing, and ungraded request metadata. It **never prints or uploads the
  model response prose**. Neither raw answer privacy nor frozen sources
  are relaxed.
- This is one isolated prompt A/B only. No inference of real semantic quality
  from lexical matches, answer length, digest differences or CI green status.
  `quality_measurement=not_measured` and
  `semantic_noninferiority=not_measured` are mandatory.

## What would count as a genuine improvement

With full, original first answers privately retained and separately
source-reviewed, compare the **same model on the same packet**
for each arm. Evaluate grounded factual conclusions, zero definitive
unsupported causal claims, full first-answer usefulness, concise natural
clarity, read-only safety, and model-request latency. A candidate should
only be promoted after comparable source-based human grading shows
noninferior or improved quality across domains. These model-only results
cannot be used as a production version A/B or Claude/Gemma parity.

**Current baseline:** Original four Qwen 3.5 4B vs Llama 3.2 3B local
captures (different local builds across cases) remain a separate historical
study. The new tiny-model prompt A/B is an entirely new experiment, and
neither its timings nor outputs may be appended to the earlier four as
though they were one population.

## CI, risk, rollback and next action

Run all repository checks plus the actual isolated model workflow.
Unit tests lock 40 unchanged source bodies, prevent hidden rubric leakage,
enforce no silent retries and null semantic scoring. Expected improvement
is **hypothetical**, not certified by the tests.

Risk: extra instruction tokens or overcautious prose could worsen latency,
naturalness or usefulness. If actual review cannot be completed, do not
enable the candidate in production or create more phrase-specific patches.
Rollback is deletion of this optional candidate renderer/runner/tests and
restoring the prior local-trial CI job. No change to production code,
model routing, rules, devices or Home Assistant configurations is needed.
