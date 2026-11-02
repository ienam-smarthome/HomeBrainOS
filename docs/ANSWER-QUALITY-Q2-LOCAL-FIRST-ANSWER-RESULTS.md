# Q2 actual local frozen-evidence first answers — measured transport, not accuracy

**Date:** 2026-11-02. **Trial PR:** [#1324](https://github.com/ienam-smarthome/HomeBrainOS/pull/1324), tested head `b18676cb153e856b0752b0a741c34478d71ac8d2`, merge commit `16dd61c6037b37164e2dadd76cf1933f9efb3acf`. **8/8 exact-head CI checks green** and **5,995 Python tests passed, two warnings**. Actual inference job: [Q2 actual local first-answer trial](https://github.com/ienam-smarthome/HomeBrainOS/actions/runs/41545402614).

## Exact fixed inputs and actual observed responses

An isolated GitHub runner, `OLLAMA_NO_CLOUD=1`, loopback-only Ollama, downloaded the public **Qwen2.5 0.5B** and **Llama 3.2 1B** tags. Each model received identical frozen source packet prompt text **once** for four curated synthetic/anonymised cases (eight real HTTP local-model requests, eight non-empty first responses, four matched prompt SHA-256 pairs). Both models used `temperature=0`, `seed=7`, `num_ctx=4096`, `num_predict=320`; no retries. Complete raw answers were not persisted or uploaded and no quality reviewer read them. The response digest and length were output without plaintext answers.

| Case | Qwen 0.5B actual wall | Llama 1B actual wall |
| --- | ---: | ---: |
| Command issuer vs reporter | 4.111 s | 8.233 s |
| Early heating OFF return | 2.704 s | 4.393 s |
| Broker connection vs endpoint health | 1.969 s | 4.895 s |
| Rule parent identity gap | 1.643 s | 4.670 s |
| **Median within these four** | **2.337 s** | **4.783 s** |

This is **actual model execution timing on one temporary shared CPU runner**, not production HomeBrain latency, not a statistically reliable model ranking or a repeatable p95. First requests may include initial model load. GitHub-hosted runner minutes may incur plan allowance; cloud-model provider inference **was not** used or billed. All four source prompts were synthetic/anonymised, no actual household Hubitat/HA reads or writes, no production model router or answer publisher involved.

## Review and release gate

**Measured:** 8/8 model requests returned nonempty first answers, same frozen prompt SHA per pair, and the displayed first-answer wall times. No raw responses available in CI for independent human source review, so **factual grounding, causal calibration, answer usefulness, naturalness, safety of generated prose and relative semantic accuracy: NOT MEASURED**. **Gemma Cloud/Claude comparison: NOT RUN**. Do not infer accuracy or model superiority from latency/completion.

**Next meaningful Q2 milestone:** A consented, privacy-preserving private capture of *actual first model answers* against the frozen packet with the same 40-case rubric. A baseline candidate should use the user's actual configured **Gemma Cloud** only after explicit cloud usage approval; compare it with an available alternative using byte-identical prompts and privately reviewed answers, attach source evidence and first-attempt metadata to the SHA-bound review CLI merged in PR #1322. If paid Cloud access or private answer reviews are unavailable, keep semantic quality **NOT MEASURED** and do not add any answer-format incident patches. Q3 should only simplify gates when demonstrated noninferior across actual reviewed answers.

**Independent upstream dependency:** Rule Machine one-time native creation stays disabled. HomeBrain cannot safely verify native app class from the currently installed MCP server. See [source-boundary proposal](UPSTREAM-NATIVE-APP-IDENTITY-CONTRACT.md); developer upstream issue/pr (or a tested fork) must supply trusted nonrendering identity and separately dated one-shot trigger behaviour. The upstream repo is read-only for this connected GitHub integration; no upstream patch is claimed.
