# Q2 private first-answer capture — fixed evidence, explicit model invocation

**Status:** tool and mocked tests, NOT a measured Gemma-vs-alternative result.
**Scope:** local/offline evaluation scripts only. No production HomeBrain model routing,
Hubitat/HA, live devices, rules, router, or add-on version changes.

## Why

The prior actual local Q2 runner generated two first-model responses for each
frozen input, but deliberately discarded plaintext answers. That proves
transport/request completion and timings, not factual reasoning. The separate
paired-review scorecard requires privately retained **exact first answers** and
answer-SHA-bound human source reviews. This tool closes that capture gap without
inventing a review or logging raw text to public GitHub Actions.

## Command and guardrails

Dry run (no network, API charges, storage or model execution):

```powershell
python scripts/answer_quality_q2_private_capture.py
```

To compare two already-installed **local** Ollama models, explicitly run
in a normal local checkout, not in GitHub Actions:

```powershell
python scripts/answer_quality_q2_private_capture.py --run --baseline-provider ollama-local --baseline-model qwen3.5:4b --candidate-provider ollama-local --candidate-model llama3.2:3b --private-dir "$env:USERPROFILE\HomeBrain-Q2-private"
```

Model names are examples, not an assertion that any given machine has these
tags installed. The local transport only reaches `127.0.0.1:11434` and
checks the local `/api/tags` inventory without downloading missing models.
Use an unused directory name; existing outputs cannot be overwritten.
Ollama local model tags and the local inventory are not independent proof
of the server's upstream connectivity configuration.

For a direct **Gemma 4 31B Ollama Cloud** arm, the supported official
endpoint is `https://ollama.com/api/chat`, with `model=gemma4:31b`
and `OLLAMA_API_KEY` supplied **only through an environment variable**.
A separate `--ack-cloud-usage` flag is mandatory in addition to `--run`.
Cloud availability, free allowance, pricing and any charge are **not**
preverified; the action may consume allowance or incur cost. Do not run
a cloud comparison without explicit individual authorisation of that
possible usage. No key or paid inference is accessed by CI or this PR.

The default selected frozen, synthetic/anonymised cases are:
`aq_command_issuer_vs_reporter`,
`aq_early_heating_off_resume`,
`aq_network_broker_vs_device_health`,
`aq_rule_parent_type_gap`. Select a smaller subset with repeated
`--case-id` arguments (1–4 only). The program sends each model a
literal rendered prompt once per case; the exact same prompt is supplied
to both arms. There are **zero retries**, no model tools and no live MCP
reads or Hubitat/HA calls. Requested settings are temperature 0,
seed 7, context 4096, prediction limit 320; provider compliance with
these sampling requests is not independently attested.

## Output and actual evaluation

Only after all requested first answers succeed, the tool creates a
new private directory **outside the repository** with restrictive
permissions where supported. It contains:

- `<case-id>.baseline.txt` and `<case-id>.candidate.txt`: raw
  original model prose; keep private and never commit.
- `baseline.json` and `candidate.json`: existing
  `homebrain-answer-quality-offline-run.v1` metadata,
  including frozen packet hash, raw answer hash, requested model/provider,
  model response wall time, `attempt_index=1` and local checkout SHA.
- `session.json`: exact rendered prompt hash per case, requested
  settings, source limitations and explicit **not_measured** status.
- `reviews-unfilled.json`: answer-digest-matched human-review
  template with **null** rubric grades, reviewer ID and evidence digest.
  The existing scorecard correctly rejects unfilled grades.

Reviewers must compare each raw answer with the *actual frozen source
evidence* and rubric from the curated case. Fill reviewer pseudonym,
evidence-review SHA, grounded/evaluated factual counts, unsupported
definitive causal claims, and all five qualitative ratings for each arm.
Then run `scripts/answer_quality_paired_reviews.py` using the two
metadata manifests and **completed** review JSON. Only genuinely
human-reviewed, exact-answer SHA-matched pairs can contribute to the
scorecard. Unreviewed answers remain **not_measured**.

## Security, limitations and rollback

The app restricts model transports to the fixed local loopback and
official Ollama Cloud endpoint, disallows HTTP redirects, avoids
proxy use on loopback, refuses to run in public CI, caps output size,
suppresses provider error bodies, refuses existing or in-repository
output paths and does not print raw model prose. OS permissions on
Windows may differ from POSIX `0600/0700`; protect the output directory.
A transport failure after an earlier cloud request may still consume
cloud allowance although **no** synthetic score or partial successful
pair is written. No automatic re-run is attempted.

Success verifies local program-requested prompt identity, not
independently authenticated provider ingestion, deployed HomeBrain
build identity, independent model first-attempt status, correctness,
Claude equivalence, p95, privacy of the provider, or production
publisher behaviour. Compare provider execution costs separately and
do not promote model-authored unsupported causal claims to production
without source-grounded review.

**Evaluation plan:** First trial one or more local-model arms without
cloud expenditure, confirm private output and manual rubric workflow,
then request specific approval if an Ollama Cloud Gemma comparison is
desired. Continue Q2 across multiple evidence domains; do not add
another single-device publication patch. Roll back this offline tool
if it can write raw answers into source control, call arbitrary URLs,
retry silently, fake grades, or bypass cloud acknowledgement.

## 4 November 2026 — first live local capture failure and bounded correction

**Observed attempt (not a completed A/B):** On a Windows PC with
`qwen3.5:4b` and `llama3.2:3b` in the local Ollama inventory, a
one-case, local-only Q2 run returned
`Q2 capture incomplete: No bounded text-only first model answer`.
The old error combines empty content, oversized content and tool calls;
without response metadata it **does not establish which model failed**.
No complete model pair or independently human-reviewed quality result was
captured. The failed invocation does not count as a valid first-answer
comparison and may not be silently re-labelled a success on retry.

**General provider-contract diagnosis:** Ollama /api/chat can return a
separate `message.thinking` field for thinking-capable models. With
`num_predict=320`, a model might use its available token budget before
returning `message.content`. The prior capture tool omitted the
top-level `think` parameter, leaving the model default in control.
Official docs: <https://github.com/ollama/ollama/blob/main/docs/capabilities/thinking.mdx>.
This is a plausible mechanism, **not an independently retained
response from the failing PC**.

**Tool change:** After verifying a tag in local `/api/tags`, the
tool now reads local `/api/show` once per model. Where Boolean no-thinking
control is supported, it requests `"think":false` at the **top level**
of `/api/chat`, not inside `options`. Non-thinking models do not receive
a thinking control. Models advertising only named thinking levels and no
off toggle fail closed, without falling back or retrying. The private
`session.json` records the new local policy. Identical frozen prompts,
temperature/seed/context/output budget, one inference attempt per arm,
raw-answer privacy and no-tool restrictions remain unchanged.
The direct Ollama Cloud request contract is **unchanged**.
The response validator differentiates thinking-only, empty text,
tool calls and output too large, naming the failing comparison arm
without printing raw model output.

**Tradeoff:** This is an explicit **answer-only** mode for local
thinking-capable models. It does not measure their quality with thinking
enabled; other model/runtime settings still require actual provider
attestation. A new invocation after the fix is a **new experiment**,
not recovery of the failed first attempt. The original unsuccessful
run retains no valid scored data.

**Acceptance:** Syntax checks and local fake-transport checks are useful,
but a genuine Windows Ollama rerun and exact-head CI are needed to
confirm whether local Qwen actually returns a usable answer. Until then,
Gemma-vs-local factual quality, local Qwen-vs-Llama quality and model
first-answer reliability remain **not_measured**. Roll back if discovery
breaks installed model calls, no-thinking controls are misapplied, or
private prompts leak into GitHub logs.

## 4 November 2026 — multi-case failure: safe stage diagnosis, not a quality verdict

**Observed user attempt:** The user ran the next three frozen cases
(`aq_command_issuer_vs_reporter`, `aq_early_heating_off_resume`,
`aq_rule_parent_type_gap`) with `qwen3.5:4b` versus `llama3.2:3b`
locally and received only
`Q2 capture incomplete: private transport or file error`.
The previously successful **single MQTT pair remains valid** and
unchanged; the three-case attempt yielded **no complete new pair,
no submitted outputs, and no scores**. The generic error hides whether
the failure was a per-request timeout, Ollama HTTP/network response,
Git checkout read, or private file write; **root cause is unverified**.
No reported timestamp, elapsed time, or case/arm failure provenance
was provided, so do not invent which case or model failed.

**Generalised offline-tool fix:** Introduce internal safe
`CaptureTransportError` categories and stage names, including
`local-model-inventory`, `local-model-capabilities`,
`local-inference`, `cloud-inference`, `local-git`,
and `private-output`. Classify HTTP status code, timeout,
connection failure, and opaque network/provider errors without
displaying provider response bodies, request URLs, prompt text,
authentication, local paths or raw socket messages. Attach the
**frozen case ID**, model/provider and baseline/candidate arm
to a sanitized failed model call. Block untrusted model
`ValueError` strings from reaching stderr; only known static
validation messages may appear. A failed output write now
returns a bounded `private-output: filesystem-write-failed`
message, acknowledging that an output folder might be partially
created and must never be overwritten. The `--timeout-seconds`
control remains bounded (1–180); don't change the budget
or silently repeat a failed case until the actual error category
is known.

**No changes** to source packets, answer-only thinking policy,
request model options, URL allowance, provider selection,
model count, retry policy, cloud consent, paid routing, installed
add-on v0.18.404, production publisher, Hubitat/HA/router/devices
or rules. Existing successful answer files remain private
outside the repository. Test the error taxonomy with fake
provider timeouts, URL wrapper failures, HTTP errors, arbitrary
secret-bearing exceptions and private filesystem errors.
These are **diagnostic-contract tests**, not live inference,
a real environmental root cause, a successful three-case trial
or an evaluated model-quality score.

**Next live action after code CI:** update the local checkout,
run the same three-case selection in a **new**, uniquely named
private directory once, and retain its response or sanitized
error. If a timeout is actually reported, a later protocol
may explicitly disclose an increased timeout for a separate
run, rather than reclassifying a failed first attempt.
