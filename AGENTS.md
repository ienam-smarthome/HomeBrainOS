# HomeBrainOS development agent instructions

## Standing mandate — do not change direction between chats

**New user direction (6 Nov 2026):** Do not keep adding per-question fixes or require the user to continually train the assistant. Build the autonomous evidence-first architecture in [docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md](docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md): model-selected evidence requirements, verified read-only execution, source-aware continuation, grounded synthesis, and evaluated improvement on unseen questions. Remove arbitrary soft limits on read-only inquiry, **not** operational deadlines, write permissions, user confirmation, privacy or resource safeguards. Phase 1 is only the first increment, not proof of general autonomy.


**Source of truth:** [docs/ANSWER-QUALITY-CHARTER.md](docs/ANSWER-QUALITY-CHARTER.md)  
**Current work, real results and handoff:** [docs/ANSWER-QUALITY-STATUS.md](docs/ANSWER-QUALITY-STATUS.md)

The user specifically requested one persistent project direction and fast-paced, evaluation-driven development. **Do not resume a sequence of case-specific stage patches.** Our job is to make HomeBrainOS consistently answer common Hubitat/HA questions with Claude-like natural clarity, strong evidence grounding and appropriate uncertainty. Progress is **measured answer improvement**, not extra version numbers or the count of passing unit tests.

**Current generative claim migration milestone (7 Nov 2026):** v0.18.455 merged through PR #1514 and verified handoff #1515. Canonical `claim_evidence_contract.py` and the host receipt adapter expose non-publishing `evidence_validation.claim_evidence_shadow`; the history-only latest-OFF route now works without optional correlation/domain markers. All four implementation-head CI workflows passed (6,747 Python tests). Installed v0.18.453 failed diagnostic acceptance; **installed v0.18.455 shadow integration passed, but full answer acceptance remains partial**. The supplied full response exposed default-past and focal log-scope gaps; v0.18.456 corrects shared request normalisation and prevents unrelated historical command decision reads (candidate CI/live acceptance pending). The sidecar explicitly has `model_claims_assessed=false`: it is not a general model claim emitter, factual grade or production publisher. Next obtain the unchanged read-only question plus full Technical JSON, preserve privacy-safe diagnostic presence in evaluation captures, then freeze diverse matched typed-claim comparisons before promoting publication or retiring guards. See [current development review](docs/DEVELOPMENT-REVIEW-2026-11-07.md).

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
