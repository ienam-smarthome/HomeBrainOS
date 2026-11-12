# HomeBrainOS V2 — opt-in frozen-receipt model replay (alpha.58 baseline)

**Date:** 12 November 2026. **State:** separate evaluation program; production V2 remains alpha.58.

## Motivation and scope

PR #1609 added a private *manual ledger*, not a way to produce comparable model answers. The follow-on runner `hubitat-mcp-ai-v2/evaluation/frozen_model_replay.py` makes a reproducible **shared-initial-draft comparison** possible without any Hubitat/MCP calls. This is not a replacement for fresh read-only source-real acceptance and does not establish which architecture retrieves evidence better.

For each frozen private first-answer capture (or a `homebrain-v2-frozen-receipts.v1` packet), the evaluator:

1. Locally reads the original question and successful/failed tool receipts; rejects any receipt with a non-read-only tool name or an unverified failed execution. Keeps the exact returned receipt payloads including failed contracts, filters, row limits and source gaps. Rejects oversize cases instead of silently truncating receipts.
2. Starts one **tool-free** model conversation with the original question and a fixed serialization of those source receipts. Uses the existing Hubitat skill/reference files plus a short explicit *frozen experiment/no tools* instruction. This is deliberately not the same as a live tool-calling transcript.
3. Captures the first answer. This is the **single-answer baseline**.
4. Continues that *same* model conversation with the repository's existing source-review prompt for the question type, then the existing final audit prompt and scope index. **No tool is offered or executed at any point.** Each stage sees the same original receipts; the later stages additionally see the previous draft. The review cannot obtain any new evidence. This isolates revision behaviour, not improvements from discovery.
5. Randomly assigns the original and final answers to blinded `A.txt` and `B.txt` files, while storing the private assignment map, intermediate draft, receipt hash, stage counts and latency in a restricted local file. Human judges must receive ONLY the blinded answers and the separately held original evidence, never the assignment map.
6. Operator later manually supplies 0/1/2 human evidence scores and runs `review_pass_pairs.py` for paired reporting. This runner does **not** assign truth scores or declare a winner.

## Example: a private local-model run

Outside the GitHub checkout, store a **PRIVATE** first-answer Technical JSON as `/private/captures/case01.json`. The runner reads `question` and `response.tool_calls` only; it never uses the previous model's `answer` or `answer_stage_trace` as a truth source.

```bash
python hubitat-mcp-ai-v2/evaluation/frozen_model_replay.py \
  /private/captures/case01.json \
  --model qwen3.5:4b \
  --output /private/experiments/case01-seed1 \
  --seed 11
```

Default target is **local** Ollama-compatible `http://127.0.0.1:11434/api/chat`; there is no automatic network request to Hubitat or any MCP server. The runner refuses non-local model endpoints unless `--allow-remote-model` is explicit **and** HTTPS is used. Ollama cloud model names containing `-cloud` or `cloud/` also require this flag even when the endpoint is localhost, because the local Ollama daemon may forward the private source data to a cloud provider. Other local proxies can likewise forward it—check the model/provider before use. Remote model use potentially discloses raw household evidence; opt in only if appropriate. An API key, if needed, is read from `HOMEBRAIN_EVAL_API_KEY` rather than CLI arguments. HTTP redirects and environment proxies are disabled.

`--output` must not exist; output and capture paths must be outside the repository to reduce accidental commits. Blinded answer files and private assignment are created in a local owner-only directory (subject to host filesystem permission behaviour). Do not upload them to issues, PR comments, tests, CI logs or public cloud storage.

## Interpretation

- Both outcomes inherit a single shared first model response. This is a *within-draft continuation comparison*; it is not two independent full agent runs, a randomized end-to-end architecture A/B, or a proof of causal efficacy on other model seeds.
- The baseline takes one model round; the reviewed condition takes three rounds (initial, source checkpoint, final audit). Report total latency vs baseline latency, including all retries and errors as applicable. If any model pass errors, the entire comparison is rejected instead of falsely counting a completed review.
- The skill references are taken from current source, but live V2 also injects a source availability summary and actually allows independent read-only tool selection at the source-review checkpoint. This replay omits both tool availability and acquisition, so it cannot test that stage's impact on source completeness.
- Run at least 12 *fresh* cross-domain questions with multiple seeds/replicates. Preserve the old Livingroom Light 2 case only as a regression control, not a fresh holdout. Use independent blind human judges where possible, with original successful receipts, timestamps, filters, row caps and missing discriminating sources explicitly considered.
- Do not remove source review or final audit, change V1 or promote V2 based on one replay. Only consider architecture changes after reviewing reproducible cross-domain score and latency deltas alongside source-real Gate B acceptance.

## Privacy and CI

The runner is **not invoked in CI**; fictional injected-model tests validate flow, source identity, unsupported tool-request rejection, remote-endpoint consent and safe blinded output behaviour. No live model, device, credential or household packet is included in the repository.

**No production changes:** no new model round on normal Ask requests, no new agent restrictions, prompt patches, source routing, historian, Rule Machine operation, native MCP call, UI change or version bump.
