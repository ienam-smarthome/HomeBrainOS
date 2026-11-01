# HomeBrainOS — permanent answer-quality charter

**Status:** active, supersedes stage-by-stage patch chasing.  
**Established:** 2026-11-01. **Default branch:** `main`.  
**Continuity entry point:** `AGENTS.md` → this charter → `docs/ANSWER-QUALITY-STATUS.md`.

## Mission (do not change direction between chats)

Build a dependable, model-independent Hubitat/Home Assistant assistant that produces natural, concise, Claude-quality **domain-specific** answers based on verified read-only evidence. Prioritise **first-attempt correctness, explanation quality and efficiency** over version counts, synthetic test totals or new architecture. This goal remains in force across future conversations until the user explicitly changes it.

The user delegates repository inspection, implementation, PRs, CI diagnosis and safe merging. The user should be asked primarily to run a **specific read-only HomeBrain question and paste the answer plus technical JSON** when a live comparison is necessary. Avoid asking for desktop access, manual source inspection, repeated confirmation or tasks the GitHub connector can perform. Never perform live Hubitat/HA mutation without express permission. Do not claim coding continues autonomously after the assistant turn ends.

## Fixed outcome targets

| Dimension | Acceptance target | Honest measurement |
| --- | --- | --- |
| Factual grounding | At least 90% of evaluated factual conclusions supported by their cited available sources | Human evidence review with trace IDs; missing evidence is **not** a pass |
| Unsupported **definitive** causes | **0** in the evaluated set | Every definitive issuer vs. upstream trigger vs. execution claim separately reviewed |
| Useful complete answer on first attempt | At least 80% | Frozen case/question; no retries or manual prompt repair counted as a first pass |
| Common status/control latency | Under 15 seconds | Median and p95, sampled separately, actual wall-time; no invented baseline |
| Complex investigation latency | Preferably under 45 seconds | Median and p95, actual wall-time; correct but slow is not conflated with correct and fast |
| Read-only/control safety regression | **0** | Blocking mock execution/permission tests plus explicit live permission gate |
| Evidence privacy | No secrets/raw private logs in benchmark outputs | Synthetic/anonymised fixtures by default; source citations, redacted excerpts |
| Claude-like explanation quality | Gap narrows on the **same** blinded, comparable cases | Manual paired assessment; lexical indicator matching never passes for accuracy |

Thresholds are **goals**, not assertions of current quality. Publish a denominator, sample count, date, model/provider, code SHA, build, repeatability, missing cases and limitations with every result.

## Fixed evaluation protocol

1. Preserve the existing `tests/fixtures/homebrain_golden_tasks_v1.json` 13-task inventory; do not silently rewrite its acceptance obligations.
2. Extend with `tests/fixtures/answer_quality_cases_v1.json`, carefully curated **case definitions**, not invented transcripts. Initial curated set must grow toward **40–50 cases**, covering ordinary status, commands, lighting, heating, ventilation, offline network/MQTT, ambiguous names, historical causality, unavailable evidence, and control/safety.
3. Keep the **same user question**, replay/source packet, evaluation rubric, model/version, permitted tool surface and time budget for before/after comparisons. Record whether a case is offline-replayable, human-evaluated, live-only, or needs capture. Do not award credit for a replay that lacks real source evidence.
4. First measure the current `main` baseline; do **not** fabricate baseline scores or declare test pass because a response is grammatically fluent or a CI test is green. `scripts/answer_quality_scorecard.py` aggregates *reviewed* outcomes only and labels unreviewed cases explicitly.
5. Review: evidence grounding, correct causal calibration, question resolution, clear explanation, unnecessary reads/latency and safety. Track first attempt separately. A model's assertions and a host-appended paragraph must not be conflated.
6. If comparative Claude answers are unavailable, compare against a **source-verified reference** and leave the Claude gap unmeasured. Never invent Claude output, paid access or benchmark scores.
7. User test requests should be one copyable prompt and ask only for **complete HomeBrain answer + diagnostic JSON**; do internal code/repo analysis yourself.
8. Do not treat a `0`-sample score as zero failures or as 100% success. Publish `not_measured`.

## Engineering policy

- **Prefer removing/simplifying complexity** and fixing source identity, canonical evidence, temporal joins, model context and tool contracts. Do not add a phrase-specific publication patch to solve a single failure.
- Separate **observed state**, **issued command**, **upstream trigger**, **app decision**, **device acknowledgement** and **physical execution**. The absence of an event in bounded history never proves it did not occur.
- Natural language should come from the model; generic verification should reject unsupported claims without replacing the entire answer with a hardcoded paragraph.
- Validate source evidence selection and interpretation across **multiple cases** before modifying provider prompts or completion rules. Compare alternative models on the same tool/evidence contract if Gemma plateaus.
- Keep read-only diagnostics and no extra Cloud calls where possible. No local IPs, tokens, raw private logs or personal household records in public fixtures.
- Treat `Hubitat MCP AI` as the maintained package (`hubitat-mcp-ai/`); keep existing CI/release gate, package version and compatibility intact.
- Every meaningful PR must record **hypothesis, expected metric effect, tests, baseline/after case results, regression risk, rollback**, or explicitly state when real eval is pending. Merge only after all required CI checks pass.
- **Two to three evaluation/improvement cycles**, then review whether quality gains justify further architecture changes or a different model. A plateau is a signal to experiment, not licence to accumulate ad hoc guards.

## Next milestones

**Q0 — reproducible baseline and continuity.** Frozen case inventory, review rubric, scorecard CLI and no-fabrication tests. Log `main` SHA and explicitly unmeasured cases. No model claim until measured.

**Q1 — source-complete evidence packets.** For real failure cases, compare source selection, missing/hypothesis provenance and output. Prioritise cross-device time-scoped reads and explicit identity—not wording patches.

**Q2 — model reasoning A/B.** Use same evidence packet through Gemma and an available alternative, keeping provider, costs and latency disclosed. Pin settings and evaluate blindly where feasible.

**Q3 — simplify publication and latency.** Remove redundant gates/calls only where quality is non-inferior and performance better. Verify status/control and investigation separately.

**Q4 — acceptance gate.** Run frozen cases on the new version, record scores and regression diff. User supplies only needed real HomeBrain Q&A. Do not proclaim “Claude level” without comparative evidence.

## Cross-chat handoff rule

At the start of every new HomeBrainOS development chat:
- Read `AGENTS.md`, this charter, `docs/ANSWER-QUALITY-STATUS.md`, and current `main` commit plus open PR/CI status. Prefer repository truth over past chat summaries.
- Report the **next uncompleted milestone**, what was verified, and what remains unmeasured.
- Continue development or needed evaluation without requesting the user to repeat the roadmap.
- At each meaningful completion update `docs/ANSWER-QUALITY-STATUS.md` with merged SHA, accepted evidence, measured/unmeasured status and the next action; use independent PRs when updating after merge.
- Do not switch back to endless patch stages or claim autonomous background development.

## Stop/continue decision

After 2–3 measured improvement cycles: **continue** if first-pass factual correctness or explanation quality improves without breaking safety; **switch or compare model** if the evidence pipeline is adequate but reasoning remains weak; **freeze feature work** if new complexity cannot deliver reproducible benefit. Preserve working read/control capabilities regardless.
