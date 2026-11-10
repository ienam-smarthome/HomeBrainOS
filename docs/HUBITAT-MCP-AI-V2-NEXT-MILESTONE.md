# HomeBrainOS v2 — Next milestone: source-real first-answer acceptance

## 10 November 2026 — Alpha.40 first-answer acceptance: command issuer is not internal decision

**Candidate:** A successful native event-history read with command rows now includes `client_command_issuer_scope`: a bounded, source-derived record of the reported command actor and event time. It does not assert that the actor's scheduling, threshold, demand or manual path fired. No automatic tool calls, deterministic causal audit or final-answer rewrite are introduced; the model still decides source selection.

**Fresh cross-domain test (not a previously exposed lighting, ventilation or heating case):** Select a genuinely new, read-only historical controller action in another device/automation class. Ask for (1) the exact command and subsequent event outcome, (2) the recorded issuer, (3) **why that issuer acted**, and (4) which competing configured mechanisms are ruled in/out by event-specific configuration, all participating inputs and callback/execution evidence. Finish with "Do not change anything." Use the installed version shown in the UI, the untouched first answer and private Copy for review/Technical JSON.

**Evaluate:** Did the model see the issuer-sidecar, then choose relevant configuration/execution reads where available—or did it stop at actor identification and infer a cause from app name/time? Check tool name+arguments, source windows/limits, chronology, actor/reporter/listener roles, current-versus-historical configuration, missing pertinent sources, errors and precise unsupported claims. Rate grounding, completeness, causal calibration and usefulness 0/1/2. A no-command history should not fabricate an actor or sidecar. Also test an independently supported positive control whose original execution and trigger receipts genuinely identify the cause.

**Guardrails:** The score of one exposed alpha.39 answer (3/8) is not model accuracy. Synthetic CI verifies code contracts only; do not claim Gemma improved until new private live first answers corroborate it. No household receipts or private identifiers in repository notes, no incident-specific rules, fixed read chains, arbitrary model-round limits or device writes.

## 10 November 2026 — Alpha.39 first-answer acceptance: discrimination without rigid paths

**Repository candidate:** Alpha.39 enriches only **successful installed-app configuration page reads** with a `client_config_source_map` describing actual fields and linked pages. It neither fetches another page automatically nor rewrites native MCP receipts. New reasoning guidance emphasises materially competing mechanisms and complete *relevant* input histories. The installed add-on version and improved model performance remain unverified until a new private live capture.

**New independent challenge:** In a fresh Ask conversation, investigate the most recent **Bedroom 1 TRV heating-setpoint change**: report the event time, its command issuer if recorded, and which of the scheduler's heat-demand, early-off or protection paths actually caused that setpoint change. Examine contemporaneous TRV/temperature events, linked controller configuration pages and any available execution traces. If several mechanisms are consistent, compare their necessary conditions and identify the missing discriminating source rather than promoting a timestamp match to proof. End with `Do not change anything.`

**Review:** Capture first answer + original `Copy for review` privately. Check if config map's linked page references and selected input groups are correctly distinguished from evidence the model actually read. Verify event time, pre/post observations, command producer versus state reporter, current versus historical settings, relevant source freshness, query windows, data limits, tool errors and whether a unique internal callback is really supported. Score 0/1/2 for grounding/completeness/calibration/usefulness. If no controller page is returned, absence of a map is expected and does not prove settings absent. Include a positive control with a genuinely supported trigger and outcome.

**Release/engineering gate:** Require clean pilot tests, repository validation, container/release assurance and post-merge checks. Avoid modifying the production reasoning loop again for one known event. Use new examples before claiming general improvement; preserve read-only test scope and existing write confirmation.


## 10 November 2026 — Alpha.38 next first-answer transfer: alternative controller paths

**Status:** `main` is `2.0.0-alpha.38` (commit `4bada4960f9f28557d2cafd619a13f22c5fbd4f3`); its four main-branch workflows succeeded. The uploaded review packet labels its UI `2.0.0-alpha.38`, but there was no independent installed build or current state verification. Its four tool calls all succeeded, so **live-schema correction was not exercised**. A successful test of the latter requires an actual rejected local argument call and subsequent model-chosen corrected read.

**New cross-domain challenge:** Investigate a new ventilation/boost event (not an earlier exposed event) and whether humidity, a scheduled cycle or manual operation caused it. The model should select the actual relevant controller configuration, the initiating command if recorded, **all participating input data** in the event-time window and execution traces where available. Treat simultaneous alignment with more than one configured timer, or more than one plausible control path, as a hypothesis-comparison problem rather than proving one path by timestamp coincidence. A missing callback log does not establish that it did not run. Report whether a source was actually queried, returned no rows, was filtered/truncated or failed. Do not create side effects.

**Suggested new-conversation question:** "Investigate why the bathroom ventilation Fan Boost most recently switched ON. Determine the event time and whether humidity demand, a scheduled cycle or a manual command initiated it. Compare the actual controller configuration, all relevant sensor readings and the nearby event/execution logs. Say what is verified versus plausible and identify missing evidence. Do not change anything."

**Scoring:** 0/1/2 for factual grounding, source completeness, causal calibration and usefulness; N/A only when genuinely inapplicable. Check both timing alignment *and whether it discriminates*, source time ranges and return limits, historical versus current settings, producer/reporter/consumer roles, every necessary input, tool failures and any surviving alternative. Preserve the unedited first answer and original private `Copy for review`. Do not coach or rerun the same answer as a new blind benchmark. The previously captured lighting event is an exposed diagnostic example and must not be the sole regression gate.

**Next engineering gate:** Only after materially independent cases show the same failure category should a domain-neutral improvement to model source choice, typed controller-contract discoverability or causal evidence sufficiency be considered. Preserve model-led tool use, existing permissions and write confirmation, and the exact original MCP receipts. Add a genuinely verified positive control to avoid training the agent to be noncommittal.


## 10 November 2026 — Alpha.38: contract-recovery transfer acceptance

**Independent live acceptance goal:** In a new, read-only investigation on a genuinely different controller/device class, determine whether the agent (a) selects relevant source classes, (b) responds appropriately to a local JSON-schema type failure using server-advertised `live_input_contract` instead of inventing parameters, (c) leaves the failed attempt in Technical JSON, and (d) names essential settings/history as unavailable if a correcting read does not succeed. A normal successful tool call that never encounters a contract error is also acceptable but does **not** demonstrate recovery.

**Suggested user question:** "Investigate why my bathroom fan most recently entered Boost mode. Identify the command issuer, relevant humidity and schedule/manual conditions, and the controller's actual settings and execution history around that time. Distinguish what is recorded from competing possibilities. Do not change anything." This is an example of the task shape; **do not use already-exposed incidents as blinded improvement evidence**. Prefer a genuinely new, independent event and preserve the original first response in a private `Copy for review` packet. Do not publish private device IDs or logs into GitHub.

**Scoring:** 0/1/2 for factual grounding, source completeness, causal calibration and usefulness; note exact source return window, event filters, reporter versus initiator, config freshness, tool failures and whether `operation_executed` was actually established. A model that tries to correct a read but still lacks evidence must explicitly qualify the conclusion. A positive control with a properly verified event-specific cause guards against excessive abstention. No automatic write retries or additional generic route/round limits.


## 10 November 2026 — Alpha.37 acceptance: correct source for the question

The UK time display and speech-readability change is merged and CI-green but does not by itself improve retrieval accuracy. **Installed version and visible formatting require a separate user-facing check.** Next evaluate whether the model selects sources that can *actually* answer an event-specific question. A synthetic success and a previous private first-answer failure are not independent evidence of a future improvement.

**One new, read-only cross-domain test:** Investigate the main heating controller's most recently reported transition into heating, using historical thermostat events, participating zone/device history and the relevant coordination/controller configuration. Determine the exact timestamp, distinguish a heat-request command from a thermostat operating-state report and identify whether the contemporaneous reason for heating can be verified. Do not infer historical demand from only current room temperatures or setpoints, and do not assume the source list is complete. End the submitted request with `Do not change anything.`

**Evaluation:** Keep the first answer and original Tool/Technical JSON private; do not retest in the same conversation to obtain a better "first" result. Check whether each returned MCP source is filtered to the correct events (a `switch` attribute filter cannot establish absence of a separate `command-off` event type), overlaps the event-time window, includes enough history, and reaches the specific relevant controller config page where needed. Separate source reporters, subscribers, command issuers and verified decision causes. Later diagnostics do not retroactively demonstrate earlier connectivity. Rate grounding, source completeness, calibration and usefulness 0/1/2; mark tool errors explicitly. A source-name match is not proof of complete configuration.

**Development gate:** If independent tests reproduce source-selection mistakes in unrelated domains, improve general reasoning/tool-description discoverability or source-coverage semantics, not case-specific code or forced read sequences. Preserve model agency, permission and confirmation checks and original evidence fidelity. Pair future negative-evidence tests with a positive-control incident whose source-specific cause is actually established.


## 10 November 2026 — Alpha.36 negative claims and continuity: prospective acceptance

**Problem class:** Models may correctly report point samples but incorrectly infer that a device or whole system *never* lost supply, had *no* command, stayed *continuously* ON, or had *only one* possible causal mechanism. A bounded event query, current snapshot or later normal report cannot prove arbitrary unseen intermediate states.

**Prospective, read-only acceptance questions (choose fresh private incidents, not known answer fixtures):**

- **Continuity challenge:** Ask whether a short outage/interruption was excluded by point telemetry before and after a gap; model should identify the source coverage and what independent observation could discriminate.
- **Negative-command challenge:** Ask whether a controller or person could have acted even though a filtered device event query has no matching row; model should compare command history, other controller sources and limits instead of asserting universal absence.
- **Cross-system challenge:** Ask whether one or two apparently idle subsystems establish that no participating member required service during a past interval; model should not project current snapshots backwards or infer unqueried members.
- **Positive control:** Ask about an event whose original successful receipts really include a trigger, specific controller execution and compatible observed state in one window; model should identify the supported cause confidently.

Run a new **Ask** conversation for each first answer, include **Do not change anything**, and use **Copy for review** privately. Score factual grounding, source completeness, causal calibration and usefulness 0/1/2 (n/a only when truly inapplicable). Record exact times, timezones, lookback bounds, command issuers versus observers, tool errors and missing discriminating reads. This is human-reviewed evidence, not a blinded population metric.

**Boundary:** No production change targeted at a particular named appliance, automation, timestamp or command. Prompt/skill guidance remains model-owned, not an answer-rewriting filter. Green CI establishes only integration; live deployment and improvement remain unverified until separately tested.


## 10 November 2026 — Alpha.35 next checkpoint: independent first-answer transfer tests

**Current code baseline:** `2.0.0-alpha.35` on GitHub `main`, merge `68729a1c` after PRs #1577/#1578, with green main-branch CI. Installed Home Assistant version is not established from a repository merge. The previously tested household incidents and frozen synthetic holdouts are **exposed**, not unseen evidence for an unbiased improvement claim.

**Objective:** distinguish `can retrieve data` from `can decide which data proves an event-specific cause`. The next practical milestone is a short, diverse, **uncoached live first-answer series** rather than modifying the agent for one device, timer or chart.

### Proposed cross-domain new-turn trials

Use privately selected devices and recent incidents in the installed UI; the themes below deliberately contain no household identifiers or actual source data.

1. **Historical switch/control investigation:** most recent switch OFF; separate explicit `off()` command issuer, device/bridge state reporter, controller settings, and the internal condition that initiated the command; check alternative configured OFF paths.
2. **Power-versus-state discrimination:** investigate a low/zero-power reading and whether a physical supply loss is established. Correlate switch, voltage and historic meter events instead of equating 0 W with OFF.
3. **Historical heating coherence:** compare a room valve's heating state to the main heating demand **at the same historical moment**, including participating zones and coordinator settings. Current idle readings cannot prove a historical no-demand condition.
4. **Independent telemetry-source comparison:** compare an external probe and native five-minute samples by **original timestamps, source basis and lookback**; a graph correlation does not prove a reboot or root cause.
5. **Positive-control incident:** when explicit triggering event, controller execution trace and resulting state are all actually returned and temporally compatible, test whether the model correctly says that cause is verified rather than hiding behind generic uncertainty.

Each question should end in **"Do not change anything."** Start a new Ask conversation, copy the unedited first response and original private Technical JSON, and review outside the repository. If installed version differs from the target or a call failed, record it; do not silently switch test conditions or rerun as though it were the first attempt.

### Acceptance dimensions

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Factual grounding | Contradicts/creates source facts | Mostly correct but material error or omission | All material factual claims match retrieved original successful receipts |
| Source completeness | Misses essential discriminating source class | Relevant reads, significant coverage caveats unresolved | Proportionate relevant reads and accurate explicit scope; no invented complete history |
| Causal calibration | Unsupported definite cause or contradicts temporal record | Properly qualified but significant logical/source weakness | Event-specific cause supported, or uncertainty correctly tied to named missing evidence |
| Usefulness | No actionable/evaluable answer | Partial but useful | Direct, concise answer plus appropriately bounded evidence |

`n/a` is allowed only where a dimension is genuinely inapplicable, not when a causal question is answered with "unknown." Distinguish *successful native receipt* from *true-world verification*. Record tool errors, source window, return limits, reporter versus actor, settings freshness and chronology separately.

**Change policy:** No production changes simply because one answer is partial or a known question was coached. Group independent new failures by general source-coverage, sequence-comparison, tool-schema or causal-assertion category. Fix at a general abstraction boundary only when observed across domains; ensure native tool autonomy, privacy, permission/confirmation checks and non-incident-specific regression tests remain intact. Keep a positive-control test to guard against excessive abstention.


**Established:** 9 November 2026. **Implementation phase:** independent measurement groundwork; no change to production agent behavior. **Baseline:** v2 repository version 2.0.0-alpha.26, or exact version/SHA captured at deployment. Do not assume that a merged build is installed.

## 10 November 2026 — Live-first development replaces mandatory A/B workflow (alpha.29)

User-directed switch: normal **Ask / Chat** is the primary live testing and day-to-day surface. **Copy for review** copies unmodified Technical JSON with a neutral evaluation request, allowing receipt-backed informal scoring without freezing a new blind A/B bank. Older experiments remain available under **Experiments (optional)**; no study data is deleted. Native Agent/tool/permission/confirmation behavior, Hub Diagnostics and installed hub settings are unchanged. Case scores are **not** independent blinded accuracy statistics. See [live review guide](HUBITAT-MCP-AI-V2-LIVE-REVIEW-WORKFLOW.md). The alpha.28 causal A/B process below is optional, not a gate for everyday UX work.

## 10 November 2026 — Historical optional gate: alpha.28 causal evidence audit

The two newly frozen alpha.27 real-source pilot pairs are now complete. Their experimental collection-ledger candidate was **not promoted** (lower factual-grounding and source-completeness scores; causal calibration not applicable). The upcoming alpha.28 opt-in evaluation adds private claim-by-claim causal review and strict comparison of original source read receipts, **without changing model-led production behavior**. Plan a fresh, cross-domain, read-only causality study with independently checked target/capability/time details, human evidence review, and explicit unanswered-source treatment. Do not reuse the exposed alpha.27 pairs, source-real ten-case captures or older fictional holdouts for independent validation. See [alpha.28 study runbook](HUBITAT-MCP-AI-V2-CAUSAL-REVIEW-READINESS.md) and [alpha.27 pilot result](HUBITAT-MCP-AI-V2-SOURCE-LEDGER-PILOT-RESULTS.md). This update supersedes the earlier "not yet captured" phase descriptions below, which are retained as historical milestone notes.

## Why this milestone exists

The frozen six-case fictional A/B evaluation was fully completed and unblinded. An extra generic investigation-completion prompt scored 36/50 vs 31/50 for unchanged baseline, but **causal calibration tied at 7/12** and the strict discriminating-source checks also tied at 10/23. Therefore the experimental prompt is **not promoted** and those six revealed scenarios cannot serve as fresh validation. These are small, ChatGPT-assisted human ratings, not independent accuracy estimates.

**Goal:** find the general source-selection and tool-schema obstacles that prevent a useful, verified answer the first time. The model remains responsible for selecting relevant live MCP reads, deciding when the evidence is sufficient and writing natural, cautious explanations. No hardcoded per-device tool plans, event-specific heuristics, fabricated source coverage or answer rewrites.

## 9 November 2026 — Phase 2: frozen source-real capture pack prepared

A new **offline-only** `hubitat-mcp-ai-v2/tools/source_real_acceptance.py` utility prepares a private, SHA-256-sealed bank of ten new read-only questions using user-supplied device/app labels and verifies the unchanged first Technical JSON exported for each. The fixed categories differ from the six revealed fictional `hold-..` tests. It detects question mismatches, duplicate request identities, self-reported prior conversation evidence, command attempts, incomplete capture, inconsistent installed version and model fingerprints. It reuses the private reviewer audit from Phase 1; it never calls a model, MCP, HA or a device and does not export original question text or receipts. It cannot prove a real source or first attempt without the operator's attestation. A human-reviewed score is permitted only for a fully captured pack without reported prior-source carryover or a device-command attempt.

See [private capture instructions](HUBITAT-MCP-AI-V2-SOURCE-REAL-CAPTURE.md). **No actual new real-hub observations are supplied yet**; first-answer factual and causal quality remain `not_measured`. A **server-enforced read-only token** is required before any source-real collection through the installed Ask UI. The production model/tool loop is not changed, and the generic synthetic prompt candidate remains unpromoted.

## 9 November 2026 — Phase 3: First ten source-real receipts supplied, preliminary review

Ten new source-real Ask Technical JSON captures were supplied for `sr-01` through `sr-10`, all reporting the same installed alpha.26 and cloud model, ten distinct request identities, **21 native tool attempts / 20 successes / one server-side error**, 29 rounds and no device-control calls. The local frozen-question manifest/seal was **not** included in the attachments, and a read-only info response reported `writeEnabled: true`; source-real origin, first-attempt isolation and actual server-token read-only permission have **not been independently proven**. Treat these as useful *real-source receipts* but do **not** label the study fully integrity-verified.

The receipt-bounded preliminary classifications were: four source-supported, four partial/qualified (including a motion sensor accidentally used as a contact test target), and two material errors. Mechanisms include wrong aggregation of returned values, bounded history assumed complete, truncated/filtered logs presented as wider coverage, a related app mistaken for the exact named target, and command/reboot intention conflated with verified effect. See [privacy-preserving case findings](HUBITAT-MCP-AI-V2-SOURCE-REAL-RESULTS.md).

**Consequence:** These ten tests are now observed and cannot be a new unseen acceptance set for a candidate trained on their findings. Preserve the original answers. Do not promote the synthetic candidate or alter production behavior based on this single, assistant-informed provisional review. Next require the **original private manifest + SHA seal**, independent source/permission verification, then a prospective A/B study on a **newly frozen** case bank with causal calibration as the primary outcome.

## Scope and sequence

1. **Review-grade capture (implemented in this phase):** Reuse the existing private first-answer Technical JSON auditor, which reports source-window limitations, tool schema rejections, tool calls, elapsed time and command evidence. An optional **separate human-review JSON** attaches claim-level factual grounding, definite unsupported causal claims, usefulness and sufficient-source assessments to the same privately ordered exports. Quality never becomes measured merely because MCP reads succeeded.
2. **Unseen source-real sample (not yet collected):** Select a frozen, previously untested set of ordinary first-attempt questions across status, lighting, device history, heating, humidity, connectivity, automation/commands and evidence-unavailable requests. Prefer a read-only upstream token and the same configured model. Preserve the exact question and full v2 Technical JSON privately; record installed build/model/provider, date, source permissions and any missing source classes. Use the same uncoached question once per subject. Do not run writes for evaluation.
3. **Independent review (not yet performed):** A human checks actual source receipts against every consequential factual/causal conclusion, missing relevant reads, historical coverage, group membership and user usefulness. Unsupported definite causes are counted by claim, not inferred from phrases. Where source records cannot be inspected, mark unverified; do not score missing data as correct. Prefer a reviewer who has not seen the candidate allocation.
4. **Mechanism diagnosis (after results):** Partition errors into: wrong/invalid tool arguments, unavailable source, failure to seek a discriminating read, erroneous interpretation of available source, unsupported causal certainty, and ineffective final explanation. Track first-attempt correctness and latency separately; do not translate tool count directly into answer quality.
5. **Prospective model-led intervention (future phase):** Only if independent new evidence supports it, test one *general* fix to MCP schema comprehension or evidence-sufficiency decisions against unchanged production, using **another new frozen** set. Model retains tool choice and natural language; schema authority and permissions stay upstream. If no significant causal improvement, reject or revise the hypothesis rather than patching these evaluated incidents.

## Private manual-review overlay: opt-in, no credentials

Existing CLI (no model, hub, network or HA calls):

```powershell
python hubitat-mcp-ai-v2/tools/first_answer_audit.py case01.json case02.json --output first-answer-summary.json
```

Until human reviews are attached, `quality_status` remains `not_measured` and grounding/usefulness/causal scores remain null.

Create a private `source-real-reviews.json` **locally**, in the same positional order as the Technical JSON files supplied to the CLI:

```json
{
  "schema": "homebrain-v2-source-real-human-review.v1",
  "reviews": [
    {
      "export_index": 0,
      "first_attempt": true,
      "source_kind": "real",
      "factual_claims_reviewed": 5,
      "supported_factual_claims": 4,
      "definitive_causal_claims_reviewed": 1,
      "unsupported_definitive_causal_claims": 0,
      "useful_first_answer": true,
      "relevant_sources_sufficient": false
    }
  ]
}
```

The numbers above are **illustrative schema values, not real HomeBrain evaluation results**. `export_index` is zero-based and refers to the position of a private export passed on the command line. Review records are optional for any unreviewed export; each position can be scored at most once. If the first attempt cannot be attested, use `first_attempt: false`. If the packet is fictional, use `source_kind: "synthetic"`; if origin is unknown use `"unknown"`. Non-real and non-first-attempt rows are **excluded** from source-real first-answer quality denominators. For `useful_first_answer` and `relevant_sources_sufficient`, use `null` rather than guess when undetermined.

Apply the human review without exporting the private answers or receipts:

```powershell
python hubitat-mcp-ai-v2/tools/first_answer_audit.py case01.json case02.json --reviews source-real-reviews.json --output reviewed-summary.json
```

The output contains descriptive score denominators, counts and anonymised receipt metadata. `quality_status` is `human_attested_partial` or `human_attested_complete` only where qualifying reviews are supplied; an empty or inapplicable review set remains `not_measured`. `grounded_claim_rate` is null if no factual claims were reviewed. The unsupported definite-cause count is null if no definite causal claims were reviewed, so a zero-denominator case never masquerades as zero unsupported causes. The tool **does not independently prove** source provenance, freshness, reviewer independence or factual correctness; those remain human attestations.

**Privacy boundary:** Keep original Technical JSON exports and private reviews outside the public repository. No raw question, answer, event row, tool argument, model label, private note, room identity or review filename is copied into the aggregate. The published script is runnable offline and never fetches source data.

## Acceptance and stopping conditions

- Capture real first-attempt denominators and source origin; do not mix the six old fictional holdouts into an unseen real sample.
- Human-review all material factual conclusions and definite cause claims; **target ≥90% grounding and zero unsupported definite causes**, with numerator/denominator reported rather than presumed.
- Target **≥80% useful first answers** across a sufficiently varied set, report insufficient relevant reads and contract errors independently.
- Compare actual model/provider, tool schema, complete source evidence, inference rounds, request latency and operator permissions fairly. Do not promote a prompt or generic engine mechanism based on synthetic CI passing.
- No automatic device control, permission bypass, native Rule Machine edits, Home Assistant changes or cloud spending occurs through this audit tooling.

**Release/integration:** This phase changes only the *offline acceptance audit* and tests/docs. Production v2 model guidance, tool loop, Hub Diagnostics, v1 and the previous blinded study remain unchanged. A later code or model intervention must have its own PR and prospective source-real evaluation.
