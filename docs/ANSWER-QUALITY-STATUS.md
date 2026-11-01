# Answer Quality — active status and cross-chat handoff

**Charter:** [ANSWER-QUALITY-CHARTER.md](ANSWER-QUALITY-CHARTER.md)  
**Last baseline assessment:** 2026-11-01; **0 independently verified frozen-prompt production reviews**, **1 anonymised source-reviewed diagnostic** from the newly supplied complete trace. The official scorecard remains **NOT MEASURED**.  
**Current maintained add-on on main:** `0.18.331` (Q1 UI simplification, PR #1228, merge `d6d457b41c039ef74c6f78c53403864d19c1e3bd`). The latest observed model answer was from `0.18.330`; **no reasoning code changed** in v0.18.331.  
**Live Hubitat/HA mutation:** none authorised by this quality programme.

## Mission status

- **Direction fixed:** benchmark-first, generalisable evidence use, natural Claude-quality domain answers, safety and efficient first-attempt resolution. This direction persists between conversations.
- **Evaluation inventory already existed:** `tests/fixtures/homebrain_golden_tasks_v1.json` has **13** target scenarios with mixed historical replay and `capture_required` statuses. There are also prior synthetic audit-reasoning and model-evaluation scripts; they are **not an independently measured first-attempt production baseline**.
- **Q0 delivered:** [PR #1224](https://github.com/ienam-smarthome/HomeBrainOS/pull/1224), merged at commit `06592de2a30aaa0e10e84209fbe9c006a242e45a`, all 3 required workflows passed. Thirteen legacy tasks plus **18 curated source packets = 31 defined cases** with reviewer rubrics, scorecard CLI, offline regression suite and dedicated scorecard integrity CI. No factual-success claims.
- **Dashboard decision complete:** [PR #1228](https://github.com/ienam-smarthome/HomeBrainOS/pull/1228) merged with all 4 CI workflows green. Old Ollama/Stage 5/Stage 6 synthetic experiments and Live Shadow are now nested under closed **Advanced testing & diagnostics**; System Check remains directly visible. Endpoints/consents preserved. This is **UI-only**, not a corrected natural-language root-cause model.
- **Q1 real-response diagnostics:** A full v0.18.330 hallway trace and a full v0.18.330 living-room command/report trace have been reviewed in the private conversation. The hallway answer over-attributed the bridge reporter; the living-room answer correctly identified a recorded OFF-command app issuer but still overstated definitive execution/causation despite an unresolved technical verdict. Wall times were **67.065s** (hallway) and **25.181s** (living-room), from **different prompts/evidence** and therefore **not an A/B speed comparison**. See [Q1 live observations](ANSWER-QUALITY-Q1-LIVE-OBSERVATIONS.md) and [anonymised source review](ANSWER-QUALITY-Q1-COMMAND-REPORT-REVIEW.md). Neither is a verified frozen first-attempt sample.
- **Baseline answer quality:** **NOT MEASURED**. Passing thousands of unit tests and release assurance does **not** measure factual accuracy or compare fairly with Claude.
- **Real evidence motivating this change:** the Hallway Light 1 investigation first overclaimed a 15-second timeout; a later answer inferred unverified periodic keep-off while disregarding four independent source-timed motion-inactive → app OFF command pairs at approximately 15.1s. The **exact original 15:29 OFF trigger remains unverified**.
- **Known model:** free Ollama Cloud `gemma4:31b` as observed in the user's last HomeBrain trace; model/provider must be documented on each new run.
- **Q1 capture tooling delivered:** [PR #1226](https://github.com/ienam-smarthome/HomeBrainOS/pull/1226) merged at `ffd5743dbfd307f281c5e2f3112dc6dea9173bb0`, all 3 required CI workflows green. The metadata-only Q&A capture script, adversarial tests and unscored historical failure review are on main; no add-on runtime update or live-device mutation.
- **Q1 source-gap capture hardening completed:** [PR #1230](https://github.com/ienam-smarthome/HomeBrainOS/pull/1230), merged at `eaf0ec2826e10925f1cc851cabe7be94b3675861` with **all 6 exact-head checks green** (full Python release gate, scorecard integrity, add-on smoke, and validation). The extractor distinguishes missing gap metadata from a reported empty gap list, reports only allowlisted source-family names and private-label counts, and **never** certifies source completeness. This was offline measurement instrumentation: no add-on runtime change, no quality-score claim. The Livingroom natural answer **and matching technical JSON have now been supplied**; only the exact input prompt and deployed SHA remain unauthenticated for the formal frozen baseline.
- **Q1 nested coverage and source review delivered:** [PR #1232](https://github.com/ienam-smarthome/HomeBrainOS/pull/1232) merged at `25f7960802d07a44f87a46245f9517e98d89893f` with **all 6 exact-head checks green**, including the full Python suite and scorecard integrity. The privacy-minimal script now correctly reads nested `investigation_coverage.sourceCoverage.missingSourceKinds`, fails closed on conflicting shapes, and records self-reported completeness and synthesis-repair counters without leaking source strings. [Anonymised real trace review](ANSWER-QUALITY-Q1-COMMAND-REPORT-REVIEW.md) documents one supported command issuer, a temporally subsequent state report, an overconfident causal framing and an unresolved technical result. No production reasoning change or measured before/after improvement.
- **Current active task: Q1 measured-baseline eligibility and follow-through.** The matching real full trace is source-reviewed privately and its metadata contract is corrected. **0 verified frozen-prompt first-attempt reviews**, **1 independent source-bounded diagnostic review**. Verify exact user prompt/deployed SHA from an existing retained receipt where possible, then build the first eligible fixed evaluation on the unchanged evidence contract; do not retcon this run into a scored sample or ask the user for the same JSON. No user device action needed.

## Milestone tracker

| Milestone | State | Evidence required to close |
| --- | --- | --- |
| Q0: durable charter + fixed inventory + scorecard | **DONE** · PR #1224 · `06592de2a30aaa0e10e84209fbe9c006a242e45a` | CI green; 31 cases defined, 0 quality reviews, empty scorecard says not_measured |
| Q1: reproducible 13 legacy + curated new cases | **IN PROGRESS — source-reviewed trace received; exact frozen run identity pending** | Full technical trace inspected and anonymised Q1 review recorded; actual submitted prompt/deployed SHA not authenticated, so 0 certified frozen-case scores |
| Q2: source-complete reasoning improvements | **Not started** | Before/after changes pass target cases and cross-domain negative controls |
| Q3: same-evidence Gemma vs alternative model A/B | **Not started** | Paired, disclosed model versions/cost/latency, human causal review |
| Q4: simplification and acceptance | **Not started** | Valid metrics and no safety regression |

## Immediate next tasks for future chats

1. Verify current GitHub `main` and Q0 merge SHA, then **continue Q1 baseline**, not another stage patch. This programme's targets are fixed in the charter.
2. Run the scorecard without reviews. Expect `not_measured`, not a success percentage. Follow [the private Q1 capture workflow](ANSWER-QUALITY-EVALUATION.md) and [historical diagnostic findings](ANSWER-QUALITY-Q1-RETROSPECTIVE.md); never equate old differently-prompted incidents with frozen before/after measurements.
3. **Do not ask for the same JSON again.** The matching Livingroom answer plus full technical JSON are in the private conversation and have been reviewed. The actual input prompt and deployed source SHA were not included in the response, so exact-run status remains **unverified**. Preserve the anonymised assessment; do not count it as a formal first-attempt score or upload raw household evidence.
4. **Registered frozen prompt:** `Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.` Keep this unchanged. The reviewed trace reports **v0.18.330**, whereas the repository's current maintained add-on is **v0.18.331**; do not label the observed answer as tested on v0.18.331. For a future exact-run benchmark, retain the actual prompt, verified running build SHA, full trace privately, provider, runtime and source bounds. Do not prompt the user to repeat this test merely to generate another differently sourced incident.
5. Establish the **first eligible** baseline for current main with an authenticated prompt/build and full private evidence. Separate current-main v0.18.331 from the received v0.18.330 diagnostic; measure grounding claims, unsupported causes, first-attempt usefulness and wall time, and keep cases with missing evidence pending. Do not turn 25.181s from one case into a median or A/B gain.
6. Make one generalising code change driven by top-scoring failure. Re-run the same frozen cases and compare measured results. If no improvement, revert or simplify.
7. Continue to 40–50 carefully reviewed diverse cases, not auto-generated filler. Compare more capable models if Gemma plateaus, then evaluate 2–3 cycles per the charter.

## Live testing contract

Only ask the user to **paste a specified question into HomeBrain (Free · Gemma unless A/B explicitly approved)** and return **full natural answer + JSON**. No device state changes or app writes. Avoid repeated ambiguous test prompts and excessive user effort.

## Update template after each development session

- Date, `main` SHA, merged PR number/version (if changed).
- Tests and CI from exact head SHA, or exact reason not green.
- Benchmark case set and **denominator actually reviewed**, with measured results or `not_measured`.
- Generalising change implemented, limitations and rollback.
- Next specific action that a new chat can execute directly.

Never replace a measured result with a subjective “Claude-like now.” Maintain a single auditable progression.
