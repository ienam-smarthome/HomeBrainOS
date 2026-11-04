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
