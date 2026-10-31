# Stage 4M — mobile-triggered cloud microtrial and private claim review

**Development-only tooling.** No active HomeBrainOS runtime imports, live reads, controls, publisher switch, model routing or automatic provider calls.

## Model identifiers

- HomeBrain's installed Ollama Online uses the model tag gemma4:31b-cloud.
- The direct Ollama hosted API is https://ollama.com/api/chat; its documented request identifier is gemma4:31b.
- Stage 4L reports transport and structured witness success, NOT factual truth or model reasoning quality.

Official model reference: https://ollama.com/library/gemma4:31b-cloud

## Option A: Trigger the tiny cloud test from GitHub on your phone

1. Open your GitHub repository **Settings > Environments** and create/open environment **ollama-cloud-evaluation**.
2. Add an **environment secret** named **OLLAMA_API_KEY**, containing an Ollama API key created privately in your Ollama account. Never paste the key in chat, a PR, a workflow input or a repository source file. A repository-level secret can also work, but the environment secret is preferred.
3. On the main branch open **Actions > Stage 4M manual Ollama Cloud synthetic microtrial > Run workflow**.
4. Select case_count **1** initially, and explicitly check confirm_billing and confirm_synthetic_only. Running may consume provider credit.
5. Inspect the **aggregate JSON** in the job logs. Up to four fictional scenarios, one request each and no retries. No model prose, source facts, prompts, secrets, IDs or artifacts are printed/uploaded. A missing key fails the preflight without making a cloud call.

There are NO PR, push or scheduled cloud triggers; job has read-only GitHub permission. The manual workflow is transport/schema validation and does not certify safety or Claude-like answers.

Actions entry: https://github.com/ienam-smarthome/HomeBrainOS/actions/workflows/stage4m-manual-ollama-cloud.yml

## Option B: Independent review of privately captured answers

On a secured local system, run Stage 4L with explicit consent and exclusive-created private output. This is a new cloud request; GitHub's aggregate-only run does not retain prose.

    cd hubitat-mcp-ai
    export OLLAMA_API_KEY="set privately in your shell"
    python tools/stage4l_ollama_cloud_trial.py \
      --enable-cloud-inference --ack-cloud-billing \
      --ack-constructed-data-only --case-limit 1 \
      --private-output /absolute/private/path/stage4l-frozen.json

Create a *blank* independently labelable template (no AI/network):

    python tools/stage4m_private_postgeneration_review.py \
      --bundle /absolute/private/path/stage4l-frozen.json \
      --template /absolute/private/path/annotations-template.json

A separate reviewer reads the PRIVATE full frozen answer and host evidence packet and labels **every** semantic implication. Each sentence requires one to five reference_atoms and integer clarity_score and usefulness_score in the range 1–5. This tool cannot prove the reviewer is independent or that every implication has been captured.

Example reference atom JSON:

    {"proposition":"physical_effect","fact_ids":["f001"],"limit":null}

Supported atomic roles are recorded_event, recorded_issuer, recorded_clock, recorded_gap, packet_limit, upstream_cause, physical_effect, absence_of_event, complete_history. packet_limit takes no fact IDs and requires a named limit (e.g. physical_ack_unverified). upstream_cause needs two distinct IDs; other roles need one.

Run the private source-proof audit against the completed review:

    python tools/stage4m_private_postgeneration_review.py \
      --bundle /absolute/private/path/stage4l-frozen.json \
      --review /absolute/private/path/annotations-completed.json

The tool outputs only count totals, unproven/high-risk implications and mean subjective review ratings. It independently reconstructs Stage 4A facts, checks the Stage 4K freeze hashes, and applies Stage 4I host proof obligations. It does not authenticate provenance or prove prose completeness. Zero unproven *labelled* claims does not prove there are no **unlabelled** unsupported claims. To compare against the current HomeBrain publisher, blind reviewers must evaluate both outputs against the same source packet.

## Safeguards

- Never commit, publish or paste household data, tokens, generated full prose or private review files.
- Ollama API key must be created privately by the account owner. The connected GitHub tools cannot retrieve secrets or create Ollama credentials.
- First billable test should use case_count 1.
- All normal CI is offline; no changes are made to the current production publisher or live Hubitat / Home Assistant.
