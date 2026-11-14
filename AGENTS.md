# HomeBrainOS development agent instructions

## V2 alpha.81 UI scope

Command-first redesign is **V2-only** (`hubitat-mcp-ai-v2/`). Do not copy, revert, modify or depend on `hubitat-mcp-ai/` V1 as part of alpha.81. V2's session-bound `Interaction` is the authoritative request-UUID approval system; no V1 ConfirmedActionCoordinator is imported. No client prompt parser, deterministic device selector, answer rewriting, fabricated model-phase timing or simulated physical outcome. Original MCP receipts and source scope remain intact; approval previews are display-only redacted structured arguments, and edited chips require decline plus a fresh model proposal. [Release note](docs/HOMEBRAIN-V2-ALPHA81-COMMAND-FIRST-UI-20261114.md).


## V2 alpha.80 clock and executed-write error integrity (14 November 2026)

The model receives a read-only client-clock arithmetic tool, never a client-selected timer, device or command. A client UTC instant with sourced IANA timezone is not an independently observed hub clock; dated/deferred native action reports require requested-versus-stored deadline comparison and independent post-write read labelling. Track the first reviewed-unsent proposal versus actual selected write arguments as private evidence, not a command gate. An HTTP 402/429 or other later model failure must preserve already-returned successful native write receipts and separate reads, with no automatic retry or claimed future outcome. The connected model keeps natural reasoning, target/command selection and approval requirements. Do not introduce paid-routing changes or household-specific aliases/patches. [Alpha.80 note](docs/HOMEBRAIN-V2-ALPHA80-TIME-GROUNDED-ACTIONS-20261114.md).


## V2 alpha.79 capability-check evidence boundary (13 November 2026)

For explicit verification of installed capabilities, distinguish tool-guide claims, application *type* catalogue IDs, independently typed *installed* app identity, exact native trigger/action fields, accepted configuration and observed execution. Natural `Check whether ... Verify ...` requests may receive one optional model-led read-only evidence check, but the model selects its own sources. Do not open mutating native forms for a read-only query, invent a supported schedule from a datetime variable example, or convert guide availability into proof of installed compatibility. No device/rule-specific planner. Keep original Gate B and alpha.78 native one-off protections. [Development note](docs/HOMEBRAIN-V2-ALPHA79-CAPABILITY-SOURCE-VERIFICATION-20261113.md).

## V2 scope clarification — 7 November 2026

The user explicitly requires `hubitat-mcp-ai-v2/` to be a clean start following the upstream Hubitat MCP server's intended behavior. Its scope includes investigation, device control, native automation and administration within the connected server/token permissions. Earlier v2 read-only-pilot restrictions and the alpha.2 frozen tool allowlist are superseded.

Use the live catalog, exact schemas, gateway discovery and upstream skill/safety guidance. Keep model-selected tools and natural answers; no v1 planners, per-question patches, deterministic answer rewriting or fixed round quotas. Preserve upstream permission gates, explicit confirmation, backups, device identity, privacy and operational resource safeguards. Use a server-side read-only token for initial investigation acceptance. Repository authorization does not permit live hub/device changes without a specific user request.

V1 instructions below continue to apply to v1; they must not silently narrow the independent v2 architecture. Current v2 scope and acceptance: [HUBITAT-MCP-AI-V2-STATUS.md](docs/HUBITAT-MCP-AI-V2-STATUS.md).


## v2 automation-authorization boundary (13 November 2026)

Alpha.76 replaces the alpha.75 prompt-regex automation veto with a structured check on the actual selected native rule writer / gateway leaf. Native automation writes require a separate operation-specific UI approval, not conversational "yes". Ordinary native device timers are unchanged. Preserve upstream permissions, backup and confirmation controls. A user must inspect a model-proposed trigger; approval alone does not validate the model's interpretation. Do not use prompt-wording classifiers to grant mutation authority.

## v2 action proposal source alignment (13 November 2026)

Alpha.77 adds one bounded *model-led pre-dispatch reconsideration* of the first native write in live Ask, with the proposal explicitly unexecuted. The model must check target identity, effect and timing against current original MCP sources and may discover other native control surfaces or a genuine one-off rule when supported. The client never maps a device, issues an alternate command or creates a scheduler. Persistent rule/helper creation after the checkpoint requires a fresh current-request native domain read and usual independent UI approval. A saved inactive native rule is an existing draft; avoid same-name duplicate creation. Recognise a recurring switch event plus wait as repeatable unless one-off semantics are independently established. Do not overstate CI as installed source-real quality.

## Standing mandate — do not change direction between chats
## v2 one-off Rule Machine correction (13 Nov 2026, alpha.78)

Keep the model responsible for selecting tools. Never interpret a repeatable Visual Rule timeOfDay as a one-off request. Use current native parent/target evidence, a dated typed Rule Machine trigger, exactly one verified Switch action and the precise `HB one-shot |` name contract for eligible one-offs. Do not infer a device's physical effect from its label. Keep independent UI confirmation and upstream backup/permission gates. Only an explicitly enabled, separately dry-run-disabled cleanup may soft-delete uniquely owned, date-attested expired rules. Do not claim installed creation, real-world outcome or cleanup verification from CI.



**New user direction (6 Nov 2026):** Do not keep adding per-question fixes or require the user to continually train the assistant. Build the autonomous evidence-first architecture in [docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md](docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md): model-selected evidence requirements, verified read-only execution, source-aware continuation, grounded synthesis, and evaluated improvement on unseen questions. Remove arbitrary soft limits on read-only inquiry, **not** operational deadlines, write permissions, user confirmation, privacy or resource safeguards. Phase 1 is only the first increment, not proof of general autonomy.


**Source of truth:** [docs/ANSWER-QUALITY-CHARTER.md](docs/ANSWER-QUALITY-CHARTER.md)  
**Current work, real results and handoff:** [docs/ANSWER-QUALITY-STATUS.md](docs/ANSWER-QUALITY-STATUS.md)

The user specifically requested one persistent project direction and fast-paced, evaluation-driven development. **Do not resume a sequence of case-specific stage patches.** Our job is to make HomeBrainOS consistently answer common Hubitat/HA questions with Claude-like natural clarity, strong evidence grounding and appropriate uncertainty. Progress is **measured answer improvement**, not extra version numbers or the count of passing unit tests.

**Current autonomous-agent milestone (7 Nov 2026):** User reaffirmed that HomeBrain must become a proper model-led Hubitat MCP assistant without continual per-question patching. v0.18.458 causal source-scope fix merged through #1521 with four exact-head workflows and 6,794 tests. New installed v0.18.457 heating trace retrieved no successful history and terminated on a guessed switch attribute; repeated user prompts are not the remedy. v0.18.459 improves the core history/reasoning lifecycle: same verified-device raw discovery after rejected dimensions, source-derived operating-state intervals and continuation for multi-part temporal evidence (merged #1522 after all four final-head workflows passed; 6,805 tests plus smoke and metadata). Installed v0.18.459 first-answer acceptance remains pending. Supplied/upstream Claude skills reviewed; live tool schemas, identities, permissions, resource safeguards and confirmation remain authoritative. Do not claim Gemma equals Claude or change paid routing without authorization. Next complete source-real acceptance and frozen cross-domain matched-model evaluation; generic model-claim assessment remains incomplete (`model_claims_assessed=false`). See [current status](docs/ANSWER-QUALITY-STATUS.md).

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
