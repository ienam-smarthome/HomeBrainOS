# Answer Quality — active status and cross-chat handoff

**Charter:** [ANSWER-QUALITY-CHARTER.md](ANSWER-QUALITY-CHARTER.md)  
**Last baseline assessment:** 2026-11-01; Q0 instrumentation delivered, **zero reviewed production answers**.  
**Current maintained add-on in main at kickoff:** `0.18.330` (Stage 9.5, PR #1223).  
**Live Hubitat/HA mutation:** none authorised by this quality programme.

## Mission status

- **Direction fixed:** benchmark-first, generalisable evidence use, natural Claude-quality domain answers, safety and efficient first-attempt resolution. This direction persists between conversations.
- **Evaluation inventory already existed:** `tests/fixtures/homebrain_golden_tasks_v1.json` has **13** target scenarios with mixed historical replay and `capture_required` statuses. There are also prior synthetic audit-reasoning and model-evaluation scripts; they are **not an independently measured first-attempt production baseline**.
- **Q0 delivered:** [PR #1224](https://github.com/ienam-smarthome/HomeBrainOS/pull/1224), merged at commit `06592de2a30aaa0e10e84209fbe9c006a242e45a`, all 3 required workflows passed. Thirteen legacy tasks plus **18 curated source packets = 31 defined cases** with reviewer rubrics, scorecard CLI, offline regression suite and dedicated scorecard integrity CI. No factual-success claims.
- **Baseline answer quality:** **NOT MEASURED**. Passing thousands of unit tests and release assurance does **not** measure factual accuracy or compare fairly with Claude.
- **Real evidence motivating this change:** the Hallway Light 1 investigation first overclaimed a 15-second timeout; a later answer inferred unverified periodic keep-off while disregarding four independent source-timed motion-inactive → app OFF command pairs at approximately 15.1s. The **exact original 15:29 OFF trigger remains unverified**.
- **Known model:** free Ollama Cloud `gemma4:31b` as observed in the user's last HomeBrain trace; model/provider must be documented on each new run.
- **Current active task: Q1 actual baseline.** Capture one exact registered current-build, read-only HomeBrain answer (start with `causal_light2_off`), independently check source evidence and grade against the frozen case. The privacy-minimal Q1 extractor and historical failure analysis are being added in this PR. **0 quality-reviewed current-build answers**; user involvement remains Q&A capture only.

## Milestone tracker

| Milestone | State | Evidence required to close |
| --- | --- | --- |
| Q0: durable charter + fixed inventory + scorecard | **DONE** · PR #1224 · `06592de2a30aaa0e10e84209fbe9c006a242e45a` | CI green; 31 cases defined, 0 quality reviews, empty scorecard says not_measured |
| Q1: reproducible 13 legacy + curated new cases | **IN PROGRESS — capture workflow and baseline** | Registered read-only first attempt + complete trace reviewed; zero fabricated pass/accuracy claims |
| Q2: source-complete reasoning improvements | **Not started** | Before/after changes pass target cases and cross-domain negative controls |
| Q3: same-evidence Gemma vs alternative model A/B | **Not started** | Paired, disclosed model versions/cost/latency, human causal review |
| Q4: simplification and acceptance | **Not started** | Valid metrics and no safety regression |

## Immediate next tasks for future chats

1. Verify current GitHub `main` and Q0 merge SHA, then **continue Q1 baseline**, not another stage patch. This programme's targets are fixed in the charter.
2. Run the scorecard without reviews. Expect `not_measured`, not a success percentage. Follow [the private Q1 capture workflow](ANSWER-QUALITY-EVALUATION.md) and [historical diagnostic findings](ANSWER-QUALITY-Q1-RETROSPECTIVE.md); never equate old differently-prompted incidents with frozen before/after measurements.
3. **Next user test (single frozen prompt):** `Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.` on current **v0.18.330**, Free · Gemma. Ask for full natural answer **and technical JSON**, note model/version/latency/receipts, and compare against the registered `causal_light2_off` task. If the user changes words, do not count it as the frozen prompt. Independently grade available source evidence; an empty history is unresolved, not passed. Later test app 4012 and other domains.
4. Establish first baseline for current main by model and latency without mixing old releases. Track source-grounded conclusion count, unsupported causal claims, first-pass usefulness and token/tool cost. Keep cases with missing evidence as pending.
5. Make one generalising code change driven by top-scoring failure. Re-run the same frozen cases and compare measured results. If no improvement, revert or simplify.
6. Continue to 40–50 carefully reviewed diverse cases, not auto-generated filler. Compare more capable models if Gemma plateaus, then evaluate 2–3 cycles per the charter.

## Live testing contract

Only ask the user to **paste a specified question into HomeBrain (Free · Gemma unless A/B explicitly approved)** and return **full natural answer + JSON**. No device state changes or app writes. Avoid repeated ambiguous test prompts and excessive user effort.

## Update template after each development session

- Date, `main` SHA, merged PR number/version (if changed).
- Tests and CI from exact head SHA, or exact reason not green.
- Benchmark case set and **denominator actually reviewed**, with measured results or `not_measured`.
- Generalising change implemented, limitations and rollback.
- Next specific action that a new chat can execute directly.

Never replace a measured result with a subjective “Claude-like now.” Maintain a single auditable progression.
