# HomeBrainOS development agent instructions

## 16 November 2026 — benchmark-first live intake merged (no V2 runtime change)

[PR #1703](https://github.com/ienam-smarthome/HomeBrainOS/pull/1703) merged as `a9037f13dd4856acc0c746823d04540b72e0f05f`, after exact-head Release assurance and Validate HomeBrain OS workflows passed. New fully offline `scripts/first_answer_live_intake.py` accepts original PRIVATE source-real V2 first-answer Technical JSON, matches only **exact read-only legacy frozen prompts**, rejects cross-chat context, native writes/unknown tools, duplicate cherry-picked cases and synthetic curated source-packet prompts improperly presented as live source evidence. Reuses receipt-only audit counts; creates an owner-only private `homebrain-answer-quality-reviews.v1` draft with SHA-256 source references and **null** human judgements. Existing scorer correctly rejects the ungraded draft; only an independent source reviewer may fill all five grades, factual/causal claim counts, reviewer and actual build SHA. V2 alpha.133, V1, native controls, authorization, model route, and the existing 53-case catalog remain unchanged. The externally supplied prose-gate regex patch is intentionally **not merged** due to reproduced false positives and false negatives. Next: obtain a few uncoached exact-case live original exports, independently review including failures, then report source-scoped subset scores with explicit denominators. Do not claim full 53-case acceptance from a few examples. [Workflow](docs/HOMEBRAIN-V2-FIRST-ANSWER-LIVE-INTAKE-20261116.md).


## 16 November 2026 — V2 alpha.132 System Health merged

[PR #1700](https://github.com/ienam-smarthome/HomeBrainOS/pull/1700) merged at `4284b84c8568cb48f7b2bb0aec07080b900a846a` after **4/4 exact-head GitHub Actions workflows passed**. Existing V2 System Health (alpha.83) already included source-only light, motion, heating-state, low-battery, contact, water, explicitly-offline and troubleshooting cards. Alpha.132 adds **recorded activity older than 24h**, derived strictly from valid timezone-aware `lastActivity` in that same original inventory: a quiet device is not a verified outage; timestamps missing/invalid/future are unknown, and count coverage is explicit. The UI also displays **cached runtime status** (configured, recorder's last saved probe, optional Hub & Device Monitor configured but untested) from the existing page-start `/api/status` response, with no extra native/LLM calls when opening System Health. Python, Node UI, Chromium smoke and screenshot checks passed. No V1, heating scheduler, model-routing, native write/approval, extra polling or new UI data endpoint changes. **Installed source-real alpha.132 inventory accuracy is not yet tested**; user should update V2 Preview and inspect the quiet-device names/source coverage, then confirm no extra calls when switching tabs. [Engineering note](docs/HOMEBRAIN-V2-ALPHA132-SYSTEM-HEALTH-FRESHNESS-20261116.md).


## 16 November 2026 — V2 alpha.131 merged; pause unverified causal-prompt patching

[PR #1698](https://github.com/ienam-smarthome/HomeBrainOS/pull/1698) merged at `47232cca1be25010368ed2dd21c20c95ab10a309` with **4/4 exact-head green workflows**. GENERAL source integrity fix: native READ-ONLY `response_too_large=true, truncated=true` envelopes are failed evidence, not successful source observations. Preserve original returned response and expose `source_limit`/model-facing notice; no automatic retry, tool choice, write, approval, V1 or heating scheduler changes. The installed alpha.130 test still failed full causal reasoning: it read a room TRV state report as if it were the shared heating output despite logs showing the controller was awaiting a two-minute confirmation. This model-led focal-output selection issue has **no verified general fix**. Stop incident-specific or prompt-only causal iterations until a measured cross-domain method exists. Resume other V2 scope development, prioritising **System Health / Troubleshooting Center** with read-only, non-LLM summaries. See [engineering note](docs/HOMEBRAIN-V2-ALPHA131-NATIVE-READ-INTEGRITY-AND-CAUSAL-PAUSE-20261116.md).


## V2 alpha.130 merged — 16 November 2026

[PR #1696](https://github.com/ienam-smarthome/HomeBrainOS/pull/1696) merged at `787728599c0abc380dbdef99c3714aca7e0c1b00` after **4/4 exact-head CI workflows green**. Installed alpha.129 first-answer scored 1/8 despite 4/4 successful source reads: the model had an original 50-row device event history and relevant native app past logs, but the final causal publication guard rejected the genuine legacy upstream `{device,events,count}` response because it lacked explicit `source=device`/`deviceId` echo; the read-only fallback also lost all genuine state events. Alpha.130 shares a validated original-request device-event identity contract across publication and partial answer, handles explicit and legacy response envelopes, rejects mismatched identity/non-device sources, and retains matching app log source checks. Fictional CI is NOT installed causal accuracy. After updating V2 Preview to alpha.130, run ONE uncoached source-real read-only WHY and check actual event-time controller demand, evidence coverage, normal vs partial answer, rounds, input tokens and elapsed. No V1, scheduler or native write approval changes. [Engineering note](docs/HOMEBRAIN-V2-ALPHA130-NATIVE-DEVICE-RECEIPT-CONTRACT-20261116.md).


## V2 alpha.129 merged — 16 November 2026

[PR #1694](https://github.com/ienam-smarthome/HomeBrainOS/pull/1694) merged at `63fd6f81ee2744521ab3aaf0566b7330cdf9cd0c` following green exact-head CI. This V2-only follow-up to alpha.128 extends the publication check to definite historical "turned on today because ..." assertions and prevents unrelated app logs/triggered listeners from satisfying the necessary controller execution-source category. Matching app logs still do NOT prove the exact internal decision. Fictional regressions passed; installed V2 alpha.129 first-answer accuracy, tokens, latency and fallback use remain UNVERIFIED. Keep model-led source/tool choice, V1, scheduler and native approvals unchanged. Next: fresh uncoached read-only WHY with complete PRIVATE original Technical JSON. [Details](docs/HOMEBRAIN-V2-ALPHA129-CAUSAL-SOURCE-SCOPING-20261116.md).


## 16 November 2026 — V2 alpha.128 merged; installed causal acceptance outstanding

[PR #1692](https://github.com/ienam-smarthome/HomeBrainOS/pull/1692) merged into main at `d8f0e33fb3ecf2ef4fcf6056deca0f6618ca05a8` after **all 5/5 exact-head GitHub Actions workflows green** (V2 pilot tests, release assurance/full Python gate, repository validation, scorecard integrity and command-first UI screenshot fixtures). V2-only: model-led outcome-first review after broad/partial inventory; controller state-app producer distinct from actual command issuer; genuine app-scoped `hub_get_logs(mode=past)` offered as a model-selected source category; compact model inventory while preserving full original PRIVATE receipts; narrow source-only partial publication floor for unsupported categorical absence/causal claims. No hardcoded home device IDs, forced native read, new review round, automatic write, changed approvals, V1 or scheduler changes.

**Do not call this a proved live causal fix**: no installed alpha.128 first-answer capture has been reviewed. Next: update V2 Preview, ask one fresh natural read-only WHY (without prescribing tools), obtain complete first answer + PRIVATE Copy for review JSON. Check controlled-output historical event receipt, app execution log/event-time input selection, verified reporter/issuer/decision distinction, `causal_claim_verification`, `answer_fallback_status`, original read scopes, tool errors, model rounds, provider tokens and elapsed time. A safe partial answer is NOT a completed event-specific cause. [Engineering note](docs/HOMEBRAIN-V2-ALPHA128-CAUSAL-PUBLICATION-FLOOR-20261116.md).


## V2 alpha.128 candidate — current implementation under CI (16 November 2026)

Three PRIVATE installed alpha.127 causal first answers completed but still
failed grounding/causation: setpoint producer confused with decision, a shared
output omitted from history before a global negative, and repeated broad
inventory/model rounds. New PR #1692 is a **V2-only** candidate: preserve
all original receipts, compact only the model-facing broad causal inventory,
show non-command app-produced state events as unverified controller leads,
distinguish real app-scoped `hub_get_logs` past logs from app-emitted
`hub_list_device_events` rows, and fail closed on a narrow set of definite
causal/absence claims without original execution category. The result is a
labelled source-only partial answer, not a fabricated reason. No fixed app
IDs, compulsory reads, V1, native writes, approvals or heating scheduler
edits. Pending exact-head CI and installed uncoached first-answer quality;
do not confuse synthetic regressions with proven live improvement.
[Engineering note](docs/HOMEBRAIN-V2-ALPHA128-CAUSAL-PUBLICATION-FLOOR-20261116.md).


## V2 alpha.127 merged — 16 November 2026

[PR #1690](https://github.com/ienam-smarthome/HomeBrainOS/pull/1690) merged as `93af6b34bdeb9ca660356ec00168ba746bad72bd` after **11/11 exact-head checks passed**. V2-only source-evidence partial completion rescue for read-only investigative MODEL failures/empty finalization: native original successful state-event receipts give bounded positive observations and strict valid field/state/date rendering, marked *partial*, without recycling an unsupported earlier draft. Native writes, approvals, V1 and scheduler unchanged. Model skill now advises source-scope reuse rather than repeated broad history calls, but there is **NO measured installed model efficiency gain** from synthetic CI. Installed alpha.127 first-answer accuracy, fallback activation rate, token usage and latency are **unverified**. Next: update V2 Preview, ask one uncoached read-only causal WHY, evaluate original receipts, what evidence was actually selected, final cause calibration and whether fallback was necessary. [Engineering note](docs/HOMEBRAIN-V2-ALPHA127-EVIDENCE-PRESERVING-COMPLETION-20261116.md).


## V2 alpha.127 candidate — reliable source-grounded partial answers (16 November 2026)

Installed V2 alpha.126 read-only causal test **FAILED 1/8**: 10 successful MCP reads, 12 rounds, 1,043,369 provider-reported input tokens, ~109s, but a final EMPTY answer despite eventually reading the actual primary-output history. The earlier speculative model draft promoted an unrelated schedule/mode event into a cause and must NOT be reused as a fallback. New V2-only original-device-receipt partial answer rescue operates ONLY on empty/failed read-only investigative completion, with strict native device/field/time/value checks, no cause inference, no extra model/tool round, no write or approval impact and explicit PRIVATE fallback status. The model still owns all source and tool selection; scope-reuse guidance discourages redundant broad history reads. No new hard-coded hub IDs, scheduler changes or V1 edits. Candidate CI and installed validation pending. [Engineering note](docs/HOMEBRAIN-V2-ALPHA127-EVIDENCE-PRESERVING-COMPLETION-20261116.md).


## V2 alpha.126 merged — 16 November 2026

[PR #1688](https://github.com/ienam-smarthome/HomeBrainOS/pull/1688) merged at `2d0150d5d2998051392b3dea32e7682f9dae0e45` after **9/9 exact-head green checks**. This addresses the installed alpha.125 **1/8** causal-first-answer regression: model investigated related zone histories while missing event-time shared-output evidence and made an unsupported denial. The new V2-only source navigation distinguishes FOCUSED inventory members from those actually read historically. The model independently chooses any proportionate offered read-only historical controlled-output source within the EXISTING causal source review, then investigates issuer/decision. Stronger final factual audit rejects categorical absent-event claims from unrelated idle/current snapshots. No fixed target/tool, extra model round, physical activation proof, V1, automation policy or write-approval change. **Installed alpha.126 source-real accuracy/efficiency is NOT yet verified**; next test uncoached read-only WHY with PRIVATE original receipts. [Engineering note](docs/HOMEBRAIN-V2-ALPHA126-OUTCOME-FIRST-SOURCE-SUFFICIENCY-20261116.md).


## V2 alpha.126 candidate — source-real outcome-first regression, 16 November 2026

Installed alpha.125 uncoached shared-output WHY investigation **FAILED 1/8**: eight successful original read-only calls, eleven rounds, ~627k provider input tokens, 49.4s server; the model read only associated zone histories and wrongly denied the shared output ever activated. A focused inventory DID include the actual shared output, but its historical state/command reports and controller execution evidence were NOT read. User-provided scheduler logs were separate from installed V2 receipts. The general alpha.126 candidate introduces an original-receipt, cross-device OUTCOME-FIRST coverage frontier plus guidance in the EXISTING causal source review and final audit: identify the historical controlled output before declaring an event absent or tracing WHY; a room sensor's idle history or a guide is not a substitute. The model independently selects any proportionate offered read-only source; no fixed target, automatic read, extra model round, V1, writes, approvals or heating controller changes. CI and installed source-real acceptance pending. [Engineering note](docs/HOMEBRAIN-V2-ALPHA126-OUTCOME-FIRST-SOURCE-SUFFICIENCY-20261116.md).


## V2 alpha.125 merged — 16 November 2026

[PR #1686](https://github.com/ienam-smarthome/HomeBrainOS/pull/1686) merged at `cfaa23e615f033926176aed0de92462cf1674100` after **9/9 exact-head CI checks green**. GENERAL read-only causal investigation improvement: original command rows with recorded app issuer are differentiated from app decision/trigger evidence, with optional focused model-selected log/input reads in the **existing** review pass. No host-fixed target, log tool or extra review round; unattempted logs do not prove missing history, and an app command cannot prove independent physical operation. V1 and actual heating scheduler code unchanged. Installed V2 alpha.125 first-answer causal evidence quality and efficiency are **NOT yet measured**. Next run ONE uncoached read-only WHY question on another automation and review PRIVATE original MCP receipts, source-complete decision evidence, chronology and token/round cost. [Engineering note](docs/HOMEBRAIN-V2-ALPHA125-CAUSAL-CONTROLLER-DECISIONS-20261116.md).


## V2 alpha.125 controller-decision source follow-through — 16 November 2026

PRIVATE installed alpha.124 heating WHY first answer: **8/8 original reads successful, 11 rounds, ~684,832 provider input tokens, 42.9s server**, verified a recorded app setpoint command but **did not retrieve controller execution logs or the historical decision inputs**; source-real score 4/8. The separate supplied scheduler logs show a demand event, pending interval and hysteresis latch, but were NOT read by installed V2. V2 alpha.125 candidate adds a **general** command-issuer-to-internal-decision frontier and a checkpoint in the already-existing causal source review. The connected model alone chooses any focused read-only controller logs or event-time input records, if offered and proportionate; no forced app/log/device, new model rounds, native write, or alteration of V1/heating scheduler settings. Exact command/state timestamps and reporter-versus-issuer boundaries retained. [Engineering note](docs/HOMEBRAIN-V2-ALPHA125-CAUSAL-CONTROLLER-DECISIONS-20261116.md). Green CI and installed source-real acceptance remain outstanding.


## V2 alpha.124 model-led historical source-type frontier — 16 November 2026

Installed alpha.123 uncoached appliance power history (PRIVATE original receipts): 3/3 read-only successful calls (native inventory, 6h native power events returning zero, separate Monitor mode=status latest-value only), no Monitor history read, no writes, 6 rounds, ~279k provider input tokens, 22.1s server. Readable published answer still incorrectly treated the absent native rows/status snapshot as an absent monitor archive and labelled a last-power-event timestamp the last non-zero reading without its value. Human score 4/8. Alpha.124 V2-only candidate adds a general receipt-derived **source-TYPE** frontier and source-review checkpoint inside the existing model-led round; monitor status is not archive history, native zero rows do not disprove separate saved bins, and the model selects (or declines) an offered relevant read. No forced tool/read, new model round, automatic writer, V1 change or installed acceptance claim. See [engineering note](docs/HOMEBRAIN-V2-ALPHA124-HISTORICAL-SOURCE-TYPE-20261116.md).

## V2 alpha.123 merged handoff — 16 November 2026

[PR #1683](https://github.com/ienam-smarthome/HomeBrainOS/pull/1683) merged at `cb936fc26fe90cf1f1bba448a84b1323cac63ffa` after **11/11 exact-head CI checks passed**. Installed V2 alpha.123 user-facing/source-real acceptance remains unmeasured; the owner-provided installed alpha.122 Freezer screenshot/PRIVATE receipt is the motivation, not evidence that the new version fixed the live answer. After install, test one uncoached read-only cross-domain question, assess concise presentation, raw HTML/JSON, original receipts, uncertainty, time labels, model rounds/tokens and elapsed time. V1 and native write/approval paths unchanged. [Engineering note](docs/HOMEBRAIN-V2-ALPHA123-READABLE-ANSWERS-20261116.md).

## V2 alpha.123 answer readability — 16 November 2026

The installed alpha.122 source-real Freezer power-history capture **did use** Hub & Device Monitor (1 native inventory + 1 monitor read, no writes) and contained useful 1–81 W sampled evidence plus 32/144 null bins, but its final first answer was unreadable: huge evidence table, displayed literal <br> and JSON, repetitive summaries. It also overstated interval-long switch ON, proven telemetry pause and verified compressor causes from a current snapshot/binned power alone. Alpha.123 V2-only candidate improves concise answer-first model guidance at the existing source and final-audit checkpoints, plus safe DOM rendering of legacy <br> and 2-column table wrapping; original receipts and V1 unchanged. Source-real gains are NOT measured. [Engineering note](docs/HOMEBRAIN-V2-ALPHA123-READABLE-ANSWERS-20261116.md).

## V2 alpha.122 merged handoff — 16 November 2026

[PR #1681](https://github.com/ienam-smarthome/HomeBrainOS/pull/1681) merged at `df368d4f923e41b044492d19aac4851f34034406` after **10/10 final-head GitHub checks passed**. This V2-only source-review ledger/conditional audit/timezone improvement is NOT installed source-real acceptance; prior alpha.121 three-case human assessments remain the only current first-answer observations. Follow up with ONE fresh uncoached read-only historical investigation from another device type; examine full PRIVATE original receipts, target and time-window coverage, cause/reporters, caps/errors, source selection, model rounds/tokens, GMT/BST. No V1, routine write-approval, or native-write behavior changed. [Engineering note](docs/HOMEBRAIN-V2-ALPHA122-RECEIPT-SOURCE-COVERAGE-20261116.md).

## V2 alpha.122 source-review ledger and audit efficiency (16 November 2026)

The owner's installed alpha.121 three independent read-only historical first answers scored 7/8 (light causal), 6/8 (TRV vs Thermostat), and 5/6 (Hallway chronological listing; causality N/A). Original receipts showed good causal restraint but weak discriminating-source follow-through, a rejected unsupported `stateFilter`, unproven historical coverage and 5/10/5 model rounds. Alpha.122 adds an original-receipt-only bounded source-coverage/value-count ledger to the EXISTING model-selected read-only review, conditionally skips a redundant model-only final audit on unchanged successful uncapped noncausal histories, and resolves typed event times from the configured zone with Europe/London fallback. It does not route tools, force Monitor, declare continuous history, weaken native write checks or touch V1. These are hypotheses until green CI and installed uncoached source-real acceptance. [Engineering note](docs/HOMEBRAIN-V2-ALPHA122-RECEIPT-SOURCE-COVERAGE-20261116.md).

## V2 alpha.121 natural event times — presentation only (15 November 2026)

Installed alpha.120 correctly found an observed light ON→OFF pair but printed raw ISO, omitted the later ON/source-reported inventory, and offered an unhelpful “unobserved transition” causal caveat. Alpha.121 should prefer natural named UK date/12-hour am-pm time with configured IANA-zone GMT/BST in all user-facing model answers and the typed temporal projection, while keeping original exact offset-aware source evidence/technical JSON. Source-reported later states, bounded inventory and event reporter may be described but cannot establish an issuer, automation trigger, physical effect or complete history. The source-review pipeline and write gate are unchanged. [Engineering note](docs/HOMEBRAIN-V2-ALPHA121-NATURAL-HISTORICAL-TIMES-20261115.md).

## V2 alpha.120 evidence-preserving temporal publication (15 November 2026)

The installed alpha.119 first answer improved to 6/8 on a single live 12-hour TRV investigation but omitted positive focal setpoint/temperature/valve and separate peer thermostat-mode observations. Keep the alpha.119 **same-device, same-state-attribute before/after** proof and uncertainty boundary. Alpha.120 adds bounded original-native positive context, not a forced historian, extra paid model round, automatic read, deterministic causal guess or write permission. Only a focal matching event query may attest focal requested lookback; peer evidence cannot substitute. Further source sufficiency and token efficiency remain unmeasured; synthetic CI is not installed acceptance. Do not change V1. [Note](docs/HOMEBRAIN-V2-ALPHA120-EVIDENCE-PRESERVING-CONTEXT-20261115.md).

## V2 alpha.83 System Health source and cost boundaries

HomeBrainOS V2 `System Health` is a local presentation of the same already-fetched `/api/overview` inventory, not a new monitoring subsystem. Do not add model calls, background polling, additional MCP native reads, prompt-text classifiers or deterministic device decisions to populate its status. Show reported names and source coverage for each recognized attribute; unknown must never be re-labelled healthy or zero. Expanding pills and preparing troubleshooting questions must not submit AI or native commands. V1 is unchanged. [Note](docs/HOMEBRAIN-V2-ALPHA83-SYSTEM-HEALTH-SNAPSHOT-20261114.md).


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
