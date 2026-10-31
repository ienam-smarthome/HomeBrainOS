# Stage 4L — consent-gated Ollama Cloud evaluation

Stage 4L provides a **manual, opt-in constructed-data test** against the owner's actual Ollama Cloud service. It introduces no active agent import, UI setting, publisher switch, Hubitat or HA read/write, model-routing change or device operation.

## Distinguishing the models

Direct cloud API: https://ollama.com/api/chat using a Bearer token from the private OLLAMA_API_KEY environment variable. Per Ollama's current docs the **hosted model ID is gemma4:31b**.

A *signed-in local* Ollama daemon can separately route model gemma4:31b-cloud through its localhost API. Stage 4L does **not** use that route. Earlier GitHub Actions Qwen2.5 3B/7B tests were local inference and cannot measure the user's cloud reasoning.

## What the code does

The CLI tools/stage4l_ollama_cloud_trial.py uses four **fixed, fictional receipts** spanning lighting, heating, ventilation, and history gaps. It reconstructs Stage 4A canonical host facts, asks for bounded natural-language proposal sentences with exact source IDs, reconstructs typed claims **from the host packet rather than the model**, checks the typed Stage 4A envelope, and uses Stage 4K to bind the whole resulting draft to receipts by SHA-256.

**Passing typed checks does not mean the free-form text is semantically correct.** Every report sets publication_approval=false, semantic_completeness_proven=false and real_cloud_quality_measured=false. Independent **post-generation** atom annotations and Stage 4K review are needed before quantitative claim-coverage scores; independent human quality judgements are also needed for naturalness and usefulness.

## Default: offline, no cloud requests

From hubitat-mcp-ai:

    python tools/stage4l_ollama_cloud_trial.py
    python -m pytest -q tests/test_stage4l_ollama_cloud_trial.py

This uses an explicitly fake deterministic author and costs nothing. Green fake-transport tests do not establish the cloud model's ability.

## Separate, explicitly authorised cloud trial

Only after permission and secure API key setup, an operator may choose up to four fixed synthetic calls. There are **no retries**.

    export OLLAMA_API_KEY="set-privately-outside-git"
    python tools/stage4l_ollama_cloud_trial.py \
      --enable-cloud-inference \
      --ack-cloud-billing \
      --ack-constructed-data-only \
      --case-limit 4 \
      --private-output /absolute/private/path/stage4l-review.json

In Windows PowerShell set OLLAMA_API_KEY in the process environment in a private session. Never put keys or private bundles in GitHub source code, workflow logs, issue comments or ChatGPT chat.

The optional private-output file is created **exclusively** with permissions 0600 on POSIX. It contains only constructed receipts, authored prose and Stage 4K hashes for a later **independent** post-generation review. Windows file permissions may differ; keep the directory private.

This PR does NOT add a GitHub workflow with secrets or invoke the real cloud API; all CI remains offline.

## Further acceptance gates

1. Obtain distinct approval for a real billable cloud trial and securely provide credentials outside source control.
2. Verify available direct-cloud model ID, complete a bounded constructed evaluation, and privately freeze outputs and sources.
3. Have independent reviewers annotate all asserted semantic claims, including unsupported causes, physical effects, history completeness and absence claims; pass references separately to Stage 4K.
4. Compare factual high-risk misses, invented implications, source coverage, readability, latency and cost against the existing HomeBrain response on the same evidence.
5. Consider a separately reviewed shadow-only runtime stage; never automatically activate a new publisher because a test suite or structured citation check passes.

Production HomeBrainOS remains unchanged by Stage 4L.
