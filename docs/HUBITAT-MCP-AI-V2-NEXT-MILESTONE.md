# HomeBrainOS v2 — Next milestone: source-real first-answer acceptance

## 11 November 2026 — V1/V2 read-only paired acceptance, no runtime release

The installed V2 alpha.51 overview is populated and its native inventory reconciles, but this is not a model answer or system audit. The next gate is **paired first-answer acceptance against V1**, not additional homepage tiles.

Use docs/HOMEBRAIN-V1-V2-PAIRED-ACCEPTANCE-20261111.md for twelve new read-only cases, fresh conversations, identical prompt text, matched model/provider where practical, absolute time windows for history and original private source receipts. Store raw data privately and validate file hashes and human-entered scores with hubitat-mcp-ai-v2/evaluation/v1_v2_pairs.py. Causal claims must be tied to command/rule/log discriminators; unknown data is not proof of absence. Score 0/1/2 with only genuinely noncausal calibration N/A; compare execution errors, missing sources and unapproved mutations independently. Never expose private device evidence or OAuth tokens in public commits.

**First case:** Run the same read-only system-health prompt once against verified installed V1 and V2 and preserve both first answers before offering corrections. Then collect a second pair for a never-before-reviewed causal latest-OFF event and a third for native Rule Machine parent identity/dated trigger evidence. Only source-real gaps justify V2 changes; do not add a scheduler, generic device historian or UI experiments by default.

## 11 November 2026 — Alpha.51 overview acceptance and V1/V2 read-only parity

**Immediate installed test:** Verify 2.0.0-alpha.51 UI/API match; opening Ask triggers a single read-only /api/overview inventory, populating four source-scoped tiles without an AI query. Inspect the number of devices actually returned; switch totals include plugs, and motion/low battery totals count only devices reporting those attributes. Missing/unauthorised inventory must display unavailable rather than fabricated zeros. Refresh should use one further read without device commands. The separate external recorder status derives from existing /api/status.

**V1 parity boundary:** V1 active rooms, lights on and scheduled system-check warnings should not be treated as equivalent to V2 switches on, available motion reports, attribute-only battery alerts or recorder status. Future source-real evidence may justify typed opt-in light/room classification and a limited system audit; do not copy V1's journal/notification stack without a demonstrated need. Continue held-out paired V1/V2 tests and Rule Machine identity work from docs/HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md.
## 11 November 2026 — Alpha.50 everyday UI acceptance and V1/V2 stage two

Verify the two-tab UI on desktop/mobile with simplified composer and answer, preserved diagnostics, approvals, conversation reset, voice and Copy for review. Confirm retired experiment panels are absent from daily navigation and scripts but isolated backend/test code and saved study data remain unchanged. Retain the alpha.49 source-real positive comparison as a previously exposed validation, not an unseen held-out case.

Next: follow docs/HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md. Collect at least 12 new read-only first-answer tests across multiple domains; compare verified installed V1/V2 on matched source/time windows, model/provider where possible. Prioritise generic source coverage and Rule Machine read-only evidence. Defer automated authoring, provider failover, scheduled audits and permanent v2 cutover until measured need. Avoid duplicating V1's incident-specific host publication patches.
## 11 November 2026 — Alpha.49 acceptance and next V1/V2 comparison gates

**Immediate:** Candidate `homebrain_read_device_monitor(mode=compare)` aligns 2–5 monitored device history reads to one explicit UTC window and returns source-derived extrema and consecutive missing/held bin runs. Relative comparisons use the last completed UTC five-minute boundary (reported explicitly); custom windows preserve user input. It uses the existing authenticated read-only monitor; no duplicate recorder. For full per-device saved-bin audit choose mode=history. A summary is not independent proof of continuous physical observation or underlying outage, even with complete bin coverage.

**Installed live acceptance:** Verify V2 `2.0.0-alpha.49` and configured/reachable monitor separately; run a completely new, read-only two-device historical comparison question without naming the tool. Check for one model-selected compare call, identical returned per-device requested UTC boundaries, correct actual saved-bin extrema, bounded consecutive missing and held runs, read-only operation and no invented physical cause. Capture Copy for review + private Technical JSON; note total tool calls, model rounds and latency. Repeat with an actual missing-history source and with sensor data of unknown per-bin report freshness. An optional summary is not a guarantee the model uses it.

**Broader V1/V2 next gates:** Read `docs/HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md`. Keep installed V1 stable; compare verified installed versions on held-out, source-real current state, historical power, threshold timing, causal latest OFF, hub reboot, Rule Machine read-only review and confirmation safety. Score grounding/completeness/calibration/usefulness per question and compare latency/cost when the provider/model are equivalent. V1's additional feature services are NOT the same as proven live first-answer accuracy. Defer Rule Machine writes, provider failover, notifications, scheduled health audit and any V2 cutover until those gate results justify them. Do not copy V1's incident-specific patches or host answer rewriters into the clean V2 architecture by default.

## 11 November 2026 — Alpha.48 source-real acceptance: exact interval, saved-bin extrema and freshness

**Failure basis:** Historical source access itself now succeeds across power, temperature and humidity. Three alpha.47 first answers exposed improper coverage terminology and sensor freshness claims, plus a 12-hour Fridge/Freezer comparison using 24-hour returned summary and missing a higher saved in-window Fridge wattage reading. This is a general evidence-schema problem, not justification for a second historian or device-specific answer patch.

**Candidate acceptance:** `homebrain_read_device_monitor` returns source-derived `saved_bin_extrema`, interval boundaries and missing-slot counts for the actual returned half-open interval. Power also returns separate `report_containing_saved_bin_extrema`, reporting held bins independently from explicit-null and absent slots. Sensor values disclose `sensor_freshness_unverified` and cannot be labelled all stale or all fresh. For a relative 12-hour request, the tool emits a real 12-hour upstream custom query instead of reusing 24-hour stats; custom start/end both required. Even with a populated grid, the physical measurement stream and real peak remain unverified. Original raw results and read-only boundaries preserved.

**Unseen acceptance cases after installed alpha.48 confirmation:** (a) two power devices over the **same exact custom 12-hour interval** containing different maxima and some held/null/missing positions; (b) a selected humidity or temperature device with both changing and unchanged saved values; (c) a negative-case time range without saved history. Inspect model tool choice, `summary.window_start_utc`, `summary.window_end_exclusive_utc`, expected/populated/missing counts, saved/report-containing extrema, and whether Gemma distinguishes timestamps of bin starts from actual monitor report-handler times. Capture private Technical JSON, score grounding/completeness/calibration/usefulness 0–2, record latency. Synthetic CI and PR merge are not independent live verification; do not change Hubitat, HA, devices or monitor archive.

## 11 November 2026 — Alpha.47 acceptance: source catalog, archive completeness, per-attribute chronology

Alpha.46's live questions demonstrated two failure types: a monitor-inventory response that inferred per-device saved data from configured selectors and files; and a PC history response that inferred archive absence after reading disjoint chunks while attributing late-morning watt values to overnight amperage timestamps. Neither attempt called the optional source-specific monitor tool; the receipts did not expose whether that tool was configured/offered. The empty native result, partial archive file and later timestamped events are not proof of historical absence or measured interval wattage.

**Next candidate:** Prefer existing Hub & Device Monitor as read-only source over duplicate polling. Expose per-Ask availability of the optional structured history tool in Technical JSON and model context (configured/offered, *not* connectivity-verified). Provide a user-invoked, one-shot, credential-free connectivity check in Ask. Add conservative original-source per-file character coverage and per-event-attribute UTC bounds; no extra native fetch, fixed tool ordering, answer rewrite or write-path change. Review historical-source inventory questions as well as time-scoped history. Preserve original receipts and show unknown gaps explicitly.

**Acceptance after CI and installation:** Verify alpha.47, inspect monitor connection result, distinguish not-configured/failed status from model nonselection. Ask a first-time historical question for a confirmed selected meter; capture \`available_read_sources\`, local monitor tool receipts, exact custom start/end, report-containing saved bins, held/unknown bins and correctness of peak terminology. Confirm raw-file fragment coverage is never mistaken for archive completeness and that watt values are not attributed to timestamps belonging to a different event name. Recheck missing-history positive control and normal current-only control. Synthetic CI does not prove Gemma source selection, coverage or correctness. No live infrastructure changed.

## 11 November 2026 — Alpha.46 status-version contract acceptance

**Blocked alpha.45 live trial:** UI/add-on metadata alpha.45, reported API status alpha.44. An Ask preflight produced no model, no MCP/monitor reads and no result; answer-quality criteria are N/A. Root cause verified in source: `/api/status.version` remained hardcoded to alpha.44 while FastAPI was alpha.45. This is an API-version contract defect, not proof of a stale image or missing device power history.

**Repair and acceptance:** Replace that duplicate literal with `app.version`, bump add-on, FastAPI and interface to alpha.46, and verify the **actual HTTP `/api/status` response** matches the mounted runtime and interface, plus config version. Maintain strict browser preflight for real mismatches. Require candidate/post-merge CI, then install alpha.46, reload browser, verify API status and `device_monitor` configuration separately, and repeat the read-only historical wattage question. Archive original MCP/monitor receipts privately. No live hub/device changes.

## 11 November 2026 — Alpha.45 source-real acceptance: optional Hub & Device Monitor history

A separate Hubitat dashboard already archives power readings locally and exposes a read-only per-instance OAuth status/history API. This source is separate from native Hubitat device events, which can return zero power rows. V1's general journal and v2's external hub diagnostics recorder do not already expose these power-bin archives to v2 Ask.

**Candidate:** Add optional private configured Hub & Device Monitor API connection with one model-owned read-only tool (status and device-specific saved measurement history). Do not import or rewrite v1, modify the Groovy app, add duplicate polling, auto-route every wattage question, or widen write permissions. Strict LAN installed-app path, fixed GET endpoints, token kept out of model tool arguments/receipts. Preserve sampled-bin vs direct report distinction, report/hold provenance, collection gaps, exact requested custom interval and the distinction between the monitor's daily estimated Wh and watts.

**Acceptance:** Verify version and configured-but-private status in the installed add-on. Ask an uncoached precise *historical wattage* question for a monitor-selected device and inspect the raw Tool receipts. A successful independent read must show \`homebrain_read_device_monitor\` in the tool-call record and source-marked saved bins with \`powerReports\` provenance, not infer archive content from the screenshot or a native zero-row result. Test a distinct monitored sensor and a missing/held bin case. Compare UTC source stamps, held versus received reports, exact requested window, returned bucket granularity, gaps, and absence of false continuous peak claims. Review same four dimensions (grounding/completeness/calibration/usefulness); synthetic CI does not verify a real model/source improvement. No source changes to the user's live monitoring app and no credential disclosure.

## 11 November 2026 — Alpha.44 acceptance: requested measurement fidelity

**Observed private alpha.43 failure:** In a time-scoped historical measurement request, the correct metric filter returned zero rows, followed by a mixed event query with different quantities/units. Gemma summarised the different data as if it answered the requested history, and inferred activity not proven by those rows. A separate current measurement does not answer the historical interval. Three successful MCP calls, no tool errors; the causal-only alpha.43 checkpoint was not eligible. Reviewer score 2/8, **one nonmatched example only**; private evidence remains private.

**Alpha.44 general change:** A broad historic-data-request gate now permits one conditional model-owned source-sufficiency review. The model checks exact requested quantity, unit, target, interval and requested statistic against original returned rows; distinguishes unobserved from zero, indirect proxies from direct samples and current inventory from historical history; and decides whether any proportionate permitted read-only MCP source is useful. Preserve the existing causal mode, original source receipt fidelity, read-only supplemental catalog and write/approval boundaries. Do not force a source chain, attach a deterministic metric verdict, automatically query Home Assistant/Tasmota or rewrite an answer. The additional model round has a latency tradeoff; inspect \`source_review_invoked\` and \`source_review_kind\` in the receipt.

**Independent live challenge:** After separate installed-version verification, capture an *unseen* historical measurement question in a different device/system class than the exposed example and another with actual matching historical samples as a positive control. Capture Copy for review and Technical JSON privately. Verify exact requested units, relative-to-absolute window, original history filters/caps, direct versus derived readings, whether additional read-only sources really existed and were independently chosen, and unsupported continuous loads/peaks/activity. Report missing samples when absent, rather than invented zero or guessed totals. Assess factual grounding, completeness, calibration and usefulness 0/1/2 against original successful receipts and note latency. Synthetic tests/CI prove software contracts, not Gemma's actual first-answer quality. No live system changes.

## 11 November 2026 — Alpha.43: autonomous evidence sufficiency

A private alpha.42 first answer failed 2/8: correct observed OFF event, unsupported external-initiation claim; only inventory and attribute-filtered state history were retrieved, not commands. The new chronology index was not exercised. This repeats an exposed case and does not establish comparative accuracy.

**Candidate lifecycle:** At the first attempted answer to an eligible causal question, the client may offer one conditional further **model** deliberation. Gemma independently reviews returned evidence versus what would distinguish plausible explanations and selects any useful permitted read-only MCP call. It may instead conclude that a cause remains unverified or that existing evidence is sufficient. No hardcoded domain path, forced MCP call, automatic tool retry, deterministic cause scoring or post-hoc answer rewrite. Noncausal requests remain single-pass. The API exposes source_review_invoked; one additional model round adds possible latency. Deadline-short requests skip this checkpoint.

**Acceptance:** Fictional tests verify both model-selected extra reads and deliberate stopping with no extra reads, unchanged MCP results, safe approval gates and noncausal bypass. Require exact-PR-head v2 pilot, repository validation and release assurance, then post-merge checks. Separately install and verify alpha.43, obtain an **unseen uncoached** read-only causal first answer from a different domain than prior lighting/heating/ventilation/dehumidifier examples, and a source-supported positive control. Inspect actual MCP tools, filters, windows, caps, chronology, command issuer versus reporter and evidence for internal execution, as well as latency. Score grounding, completeness, causal calibration and usefulness 0/1/2 against original successful receipts. Do not use synthetic CI as proof of live Gemma improvement. Do not commit private household evidence or change live systems.

## 10 November 2026 — Alpha.42 acceptance: chronological evidence before causal attribution

**Candidate:** A new passive `client_event_chronology` sidecar accompanies successful native history reads that return both timestamped command and non-command rows. It sorts bounded recent command and earliest/latest per-name observation landmarks by **parsed UTC instants**, retaining source stamps and explicit omission counts. This is only an aid for reading returned evidence, not a causal pairing, clock-synchronization proof, complete history or extra MCP call. Model guidance asks for strict recorded ordering and distinguishing latest state report from latest command.

**Live independent first-answer challenge:** After separately installing and verifying `2.0.0-alpha.42`, choose a new read-only event in a domain not exposed by the previous heating, lighting, ventilation or dehumidifier cases. Ask the uncoached normal-model question *why did the event happen? Do not change anything*. Capture Copy for review and full private Technical JSON. Check the installed source version; exact chronology (including offset, milliseconds and possible clock skew); report versus command versus issuer; relevant lookback, filter and row limit; whether the first answer uses a source-derived landmark without reversing timestamps; and whether it seeks discriminating configuration/execution sources or leaves cause unverified. Rate grounding, source completeness, causal calibration and usefulness 0/1/2 against original successful receipts, not the assistant's own claims.

**Positive control and safety:** Evaluate a separate case where contemporaneous command/execution evidence genuinely supports the command-to-state mechanism, as well as a contradictory later-command case. No source order may be rewritten to manufacture a cause. Do not claim model improvement from synthetic CI or reused examples. No private records in public notes; do not add forced tool calls, rules tied to real devices, mandatory review rounds, arbitrary quotas or live device operations.

## 10 November 2026 — Alpha.41 first-answer acceptance: evidence role before origin

**Candidate:** Native event-history model output now presents (a) the requested attribute filter versus the upstream response's reported filter, (b) returned command/non-command and reporter/physical/listener rows, and (c) explicit limits on treating `producedBy`, `type: physical`, or `triggered[]` as proof of who *initiated* the action. Model guidance now makes report-versus-command-versus-execution roles more salient. This adds no data read; it does not change the upstream native MCP payload, force tool sequences or rewrite answers.

**Fresh independent acceptance:** After installing and verifying `2.0.0-alpha.41`, select an uncoached historical event from a **different automation/device class than the exposed alpha.39/40 examples**. Ask: "Why did [target device or controller action] most recently occur? Do not change anything." Capture first answer, Copy for review/Technical JSON and installed version. Inspect exactly which tool calls succeeded; whether history was filtered, command rows and proper issuer were read, controller input/config/execution evidence discriminated plausible causes, and reporter versus issuer versus downstream listener stayed separate. Score grounding, completeness, causal calibration and usefulness 0/1/2 against original receipts. Avoid reusing a previously exposed event to claim generalisation.

**Positive control and guardrails:** On a separate synthetic or source-real fully supported cause, confirm the model can state a causally verified explanation and does not always default to unknown. No private source artifacts in public GitHub notes, writes, fixed post-answer audits, arbitrary tool quotas or false population-level model-accuracy claims. CI tests source presentation and regression safety only.

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
