# HomeBrainOS development agent instructions

## Standing mandate — do not change direction between chats

**New user direction (6 Nov 2026):** Do not keep adding per-question fixes or require the user to continually train the assistant. Build the autonomous evidence-first architecture in [docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md](docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md): model-selected evidence requirements, verified read-only execution, source-aware continuation, grounded synthesis, and evaluated improvement on unseen questions. Remove arbitrary soft limits on read-only inquiry, **not** operational deadlines, write permissions, user confirmation, privacy or resource safeguards. Phase 1 is only the first increment, not proof of general autonomy.


**Source of truth:** [docs/ANSWER-QUALITY-CHARTER.md](docs/ANSWER-QUALITY-CHARTER.md)  
**Current work, real results and handoff:** [docs/ANSWER-QUALITY-STATUS.md](docs/ANSWER-QUALITY-STATUS.md)

The user specifically requested one persistent project direction and fast-paced, evaluation-driven development. **Do not resume a sequence of case-specific stage patches.** Our job is to make HomeBrainOS consistently answer common Hubitat/HA questions with Claude-like natural clarity, strong evidence grounding and appropriate uncertainty. Progress is **measured answer improvement**, not extra version numbers or the count of passing unit tests.

**Current generative claim migration milestone (7 Nov 2026):** v0.18.451 merged through PR #1506: canonical `claim_evidence_contract.py` is pure offline shadow-only, translates source-attested V1 witnesses, applies role/clock/focal/coverage gates, and passed 6,720 regression tests. This is not yet an installed model claim emitter or production publisher. Do not assume a model's `scope=context` authorises historical evidence, or a v1 target coverage summary proves negative history. Next obtain the installed v0.18.450/451 read-only acceptance, wire only safe shadow comparison at an existing evidence/answer checkpoint without new tool rounds, freeze a diverse matched packet evaluation, then promote claim-validated publication only if held-out factual support and first-answer usefulness improve. This supersedes any suggestion to add further per-device phrase guards.

### Every new development chat

1. Read the charter, current status, case manifest, current `main`, last merged PR and active PR/CI checks. This repository takes precedence over a previous chat's partial recollection.
2. Continue the next recorded benchmark/development milestone automatically within the active conversation. Do not ask the user to restate the goal or gain desktop access for tasks possible through the GitHub connector.
3. Use the current baseline and fixed cases; compare changes against the same evidence. No unmeasured claims of Claude equivalence, percentage accuracy, or “all good.”
4. Inspect code deeply, implement generalisable improvements, run available CI and merge a PR **only when all required checks are green**. Never live-change Hubitat/HA devices, configurations or automations without specific consent.
5. Update the persistent status/handoff so a new chat can pick up without losing direction. Ask the user only for specific **read-only HomeBrain questions/answers with diagnostic JSON** where a fresh live source is necessary.
6. No autonomous background coding is implied; continue actively when the conversation is resumed. Never promise future unattended implementation.

### Anti-patterns

Do not add new room-specific/source-string rules to cure one answer. Do not inflate confidence from a command issuer into the app's actual trigger; from a state report into physical confirmation; or from an empty bounded page into verified absence. Do not add unnecessary AI/tool rounds, conceal latency, fabricate reference answers, or count lexical indicators as accuracy.

### Acceptance rules

Use targets in the charter (≥90% grounded factual conclusions, **zero definitive unsupported causal claims**, ≥80% useful first answers, status/control under 15s, zero safety regressions). Complex investigations have **no fixed wall-time acceptance cutoff**; measure duration separately and prioritize grounded, complete, useful findings. Existing operational deadlines and safeguards still apply. Until real reviews establish denominators, mark metrics **not measured**. Existing release gates are necessary but not evidence of answer quality. Maintain original user data privacy and read-only default.

### Primary project

`hubitat-mcp-ai/` is the maintained Home Assistant add-on. The legacy alternate dashboard is retired. Open a focused PR for changes, capture CI results and review relevant regression tests. Keep the current version unchanged for documentation/benchmark-only PRs unless production behavior actually changes.
