# HomeBrainOS v2 — first-answer quality measurement (original development)

**Established:** 8 November 2026. **Baseline:** alpha.16; **source-gap trial:** installed alpha.17; **UI-only release:** alpha.18 (confirmed in latest export). Alpha.18 does not change the model or native-tool reasoning; installed copy-button visual feedback is not independently verified.
**Purpose:** Resume the clean, model-led MCP investigation roadmap after the Hub Diagnostics chart work. Follow the permanent Answer Quality Charter without importing V1 planners, hardcoded incident fixes, answer rewriting or tool restrictions.

## What earlier installed v2 trials did and did not show

- Native flat MCP mode performed better than the earlier gateway interface in one **matched** alpha.12 reboot question: gateway ON took 13.779s, 4/8 successful attempts; flat mode took 5.792s, 1/1 successful attempts. One pair is not a stable performance distribution or a causal proof of speed.
- Further flat first answers successfully read light events, automation settings, both relevant motion sensors and bathroom humidity thresholds.
- A lighting investigation identified the app that issued the OFF command and a 15-second sensor inactivity pattern, but **did not independently read the internal timer callback**. The explanation was strongly supported, not proven as exclusive.
- A heating investigation correctly discovered one TRV heating alongside the main thermostat, but omitted that TRV's setpoint source from a later comparison, then incorrectly said **no TRVs** had setpoint events. It also treated some app-issued commands as observed changes. Successful tools are not sufficient for a complete answer.
- Bounded history, source timestamps and empty attribute-filtered results do not establish exhaustive native retention or the absence of earlier events.
- An answer produced after previous conversation receipts is not independent in the same sense as a fresh first answer. An observed read-only sequence is not proof of read-only MCP token permissions.

Alpha.14 already added a short generic instruction concerning group membership, attributes, intervals and commands-vs-state. **Its effect has not been separately measured.** Avoid adding a claim veto, second answer model, preordained tool sequence or device-specific patch until a cross-domain first-answer baseline exists.

## Private-source evaluation workflow

1. Use a **New conversation** for each frozen question. Keep model, live native flat catalog, permissions and connected sources stable within a comparison. Do not coach the model with tool names, retry prompts or corrections.
2. Save the *first* complete answer and its browser **Download JSON** Technical details. Preserve failed first attempts; store raw exports privately, never in the public GitHub repo.
3. Run the standalone offline importer on private exports:

       python hubitat-mcp-ai-v2/tools/first_answer_audit.py /private/path/run.json --output /private/path/audit.json

   Multiple export paths are accepted. It contacts neither Hubitat nor any model, and never outputs the original question, answer, device IDs, tool arguments, source event text, error details or event timestamps.
4. The report describes browser/server latency, model rounds, native successful/failed attempts, locally rejected arguments, schema-only reads, prior context, distinct *requested* target/attribute counts and event rows from **successful native source receipts only**. Failed, rejected and metadata-only responses do not count as history even if they contain event-scope-looking text. A summed row count is **not** a unique-event count across overlapping receipts. The public-safe report emits only a model fingerprint and aggregate tool/argument-field counts, not arbitrary external model names, tool names or argument keys. Audit schema v4 includes **separate structural device-event and native-log receipt metrics** and preserves **not_measured** quality fields; neither source class establishes exhaustive history. **It does not grade correctness** or claim that requested targets actually returned complete observations.
5. Independently review actual private receipts for factual grounding, causal calibration, complete group/attribute/time scope, source command-vs-observation roles, first-response usefulness and safety. Record pass/partial/fail **only after review**. Unknown cases stay NOT MEASURED.
6. For comparisons use the same uncoached question and live evidence scope, and report each model/build, sampling denominator and latency separately. Complex-investigation seconds are descriptive; there is no quality pass/fail cutoff.

## Frozen cross-domain native-tool first-answer questions

| ID | Exact question | Reviewer checks |
| --- | --- | --- |
| V2-R1 · Reboot | Investigate the most recent Hubitat reboot. Determine whether it was caused by critically low memory, a firmware update, or another cause. Check available system events and diagnostics. Distinguish verified evidence from possible explanations. Do not change anything. | Matching systemStart, firmware/lowMemory and competing causes; historical coverage. |
| V2-R2 · Lighting | Investigate why Hallway Light 1 turned OFF most recently. Identify the recorded command issuer, investigate what caused that command, and correlate relevant automation settings and sensor history. Distinguish verified causes from possible explanations. Do not change anything. | App command issuer, bridge state reporter, sensor timing, internal callback uncertainty. |
| V2-R3 · Humidity | Investigate the most recent time the Bathroom Meter humidity went above 70%, and identify when it subsequently dropped below 60%. Calculate the elapsed time if the required historical readings are available. Clearly state any missing event coverage or uncertainty. Do not change anything. | Returned threshold events, timestamp arithmetic, sample vs exact crossing and incomplete retention. |
| V2-R4 · Heating | Investigate the most recent occasion when the main Thermostat was heating while the room TRVs appeared not to need heat. Compare their actual historical operating states and setpoints at the relevant times, and determine whether all room TRVs were genuinely idle. Identify evidence gaps rather than using today's readings to infer past conditions. Do not change anything. | All relevant TRVs, state and setpoint attributes, source event vs command, pre-window transitions. |
| V2-R5 · Ventilation | Investigate the most recent activation of FanBoost. Determine whether evidence supports humidity-triggered boost, a scheduled cycle, or a manual action. Compare relevant automation settings, event history and humidity readings at the time. Identify any unverified cause. Do not change anything. | Source selection, alternative cause discrimination, missing rule execution trace, bounded event coverage. |
| V2-R6 · Offline | Investigate the most recent occasion a device became offline or unresponsive. Identify what the hub actually recorded and distinguish a device outage from stale telemetry or an MQTT session problem. State which causes remain unverified. Do not change anything. | Current status vs historical lastSeen, reporter identity, competing explanation boundaries. |

These cases test **read-only** investigation. They do not authorize a device change or permission modification. Control/write safety belongs to isolated mock permission/approval tests, not actual write probes. The existing 40 curated offline source packets remain a separate, frozen reference set; passing an offline replay is not proof of live v2 tool autonomy.

## Fixed charter targets and present status

| Quality measure | Target | Verified baseline status |
| --- | --- | --- |
| Grounded factual conclusions | At least 90% | Not measured across a complete claim-reviewed denominator |
| Unsupported definitive causes | 0 | Qualitative errors observed, exact total not measured |
| Useful first answers | At least 80% | Not formally measured |
| Common status/control latency | Under 15s median and p95 | Not measured as a comparable set |
| Complex investigation latency | Observational only | Individual times documented, no quality cutoff |
| Read-only/control safety regressions | 0 | Synthetic CI only; live per-client permission grants not verified |

## First source-reviewed V2-R5 live result (8 November 2026)

A private, uncoached `2.0.0-alpha.16` / Gemma cloud Technical JSON was reviewed **directly against every retrieved MCP response**. The original private export remains outside GitHub. This is **one case only** and must not be represented as a model-wide first-answer quality percentage.

- **Observed:** 18.480 s client, 18.359 s server, six model rounds, 13/13 successful direct leaf reads, zero contract errors or prior evidence receipts. Three native event-history responses returned **19 total rows** (not necessarily unique), including one request at its 10-row limit. A broad device-inventory query also returned substantial unrelated context.
- **Supported:** Native switch command history identified the issuing controller app and the later physical state reporter. The configured scheduled start and duration aligned strongly with that activation. The **scheduled-cycle hypothesis was well supported**.
- **Not supported:** The answer said all monitored humidity sensors were below threshold at the focal moment, but one configured sensor had **no historical read**, and the two queried sensor histories contained **no humidity observations inside the decisive onset interval**. Later values and current state cannot fill that historical gap. No internal scheduling callback/decision trace was retrieved to establish the precise cause or to exclude all manual/other influences.
- **Reviewer disposition:** **PARTIAL first answer**: informative and directionally correct, but it asserted that the cause was fully verified and there were no unverified causes. This is a **source-reviewed causal overclaim and a historical group-member coverage gap**, not a tool-protocol failure. No global factual-claim percentage is assigned from one result.
- **Safety:** The exported operations were read-only; effective per-client Write-denied permissions are **not independently established**. No changes are inferred or authorised.
- **Next comparison:** preserve the original model-led architecture, collect a fresh uncoached cross-domain V2-R3 humidity answer, and distinguish actual returned event rows from complete historical windows before choosing any runtime change.

**Offline audit interoperability gap found:** The direct `hub_list_device_events` responses were normal native MCP `content[].text` payloads with real `events` arrays but **without** the optional `client_event_source_scope` annotation. Earlier audit versions counted **zero** scope receipts despite the successful reads. The new evaluation-only parser recognises both the native flat and gateway event shapes, counts only successful native returned rows, flags at-limit responses without inferring truncation/retention, and retains `not_established` completeness and unique-event counts. No prompt, model loop, tools or Hubitat runtime is changed.

## V2-R3 historical humidity — independent first-answer review (8 November 2026)

The second independent first-answer run used installed alpha.16 and the same cloud model, in a new conversation. Its private Technical JSON was independently reviewed and remains outside GitHub.

- **Measured:** 9.808 seconds browser, 9.740 seconds server, three model rounds, two successful native MCP reads, zero tool failures, zero prior receipts. The targeted event-history response contained 11 returned events in a 24-hour relative window, below the requested limit of 100.
- **Supported:** The model retrieved the correct historical event sequence and accurately calculated elapsed time **between returned threshold-crossing observations**.
- **Unsupported:** It declared the event stream contiguous, free of observation gaps, and proof of uninterrupted conditions during the interval. Reported events with `isStateChange:true` do not establish complete native retention, continuous measurement or the precise unobserved transition time; the focal returned series includes a material reporting interval without intermediate observations.
- **Reviewer disposition:** **PARTIAL first answer**: useful retrieval and arithmetic, but unjustified historical continuity and degree of certainty. Read-only operations do not prove effective Write-denied client grants.
- **Two-domain baseline:** Both V2-R5 ventilation and V2-R3 historical humidity were independently reviewed as partial first answers. Together they made 15/15 successful native reads, yet each overstated what the event sources proved. This is **not** a representative model-wide accuracy rate.

### Alpha.17 transferable improvement hypothesis

Both cases reveal overinterpretation of **bounded event observations**. The existing `client_event_source_scope` note marks retrieval and retention limits, but does not surface observed spacing or explicitly qualify uninterrupted state between returned events.

Alpha.17 proposes only generic event-source metadata: adjacent returned timestamp pair count, largest UTC-normalised interval between returned rows, and `can_infer_uninterrupted_state_between_events:false`. This does not add an investigation planner, extra model pass, answer-rewriting rule, tool restriction, separate inference model, or Hubitat write. The original MCP response stays intact.

**Hypothesis:** salient source-time gap metadata may reduce unjustified model certainty about unobserved intervals. **Expected effect:** fewer unsupported continuity claims at similar tool count and latency; not proven by unit tests. **Risk:** context overhead, model may ignore metadata, mixed-attribute intervals are not per-attribute coverage. **Rollback:** return to alpha.16. **Acceptance:** same frozen V2-R3 question on installed alpha.17, inspect actual source-window drift and first answer, then test transfer on a distinct frozen domain. Never grade from synthetic tests.

## Installed alpha.17 matched-question acceptance — reviewer result (8 November 2026)

The user supplied a **fresh first answer and private Technical JSON** from installed `2.0.0-alpha.17` using the same cloud model and **identical frozen V2-R3 question** as the prior alpha.16 baseline. Source evidence was reviewed directly, not inferred from model prose. Both first answers reported no prior evidence receipts. Raw household observations and event timestamps stay outside the public repository.

| Review axis | Alpha.16 | Alpha.17 |
| --- | --- | --- |
| Browser elapsed | 9.808 s | 7.886 s |
| Server elapsed | 9.740 s | 7.841 s |
| Native attempts | 2/2 successful | 2/2 successful |
| Model rounds | 3 | 3 |
| Returned events | 11 | 11 |
| Shared historical event rows (exact timestamps and values) | \u2014 | 10 of 11 |
| Observed threshold-to-threshold arithmetic | Correct | Correct |
| Unsupported uninterrupted-history assertion | **Yes** | **No** |
| Explicitly acknowledges discrete samples | Weak/inconsistent | **Yes** |
| Precision of actual versus first-*recorded* threshold times | Incomplete | Still incomplete |

The source catalog and model were held constant; the extra event in the later export and absence of the earlier oldest event reflect a moving live data window. The new `client_event_source_scope` fields were actually present in the model-visible receipt: 10 adjacent parseable returned timestamp pairs, a non-null maximum source-timestamp separation, and `can_infer_uninterrupted_state_between_events:false`. These are **source scope markers**, not independent proof of intermediate conditions. Comparing model text to source records shows the major error was removed: alpha.17 no longer declares that the entire humidity interval was continuously observed or that intermediate values were necessarily unchanged.

**Remaining issues:** The answer still phrases the *first returned above-threshold reading* as the physical crossing instant, says the crossing could have occurred *slightly* earlier without a bounded uncertainty estimate, describes the highest **returned** reading as an unrestricted physical peak, and says the two events belonged to the same “session” without establishing a source-defined session. The correct quantity is elapsed time **between the first relevant recorded observations**, not proof of continuous exposure above or below either threshold. Assessment: **improved PARTIAL** on one matched question, not a full pass or measured model-wide quality rate. Two calls and three rounds held constant. The 1.922 s observed browser-speed difference (19.6%) is descriptive, not demonstrated repeatable latency improvement.

**Decision:** The alpha.17 sidecar hypothesis has **one positive installed acceptance**, but it is not yet independently validated across domains. No new incident-specific prompt, planner, second model, forced tool use, or answer rewrite is justified. Retain `2.0.0-alpha.17`, and next run a distinct frozen first-answer investigation (V2-R2 lighting causality) with its unmodified wording and private Technical JSON. Grade historical sensor coverage, command issuer vs physical reporter, internal automation execution uncertainty, model-selected reads, and resource use. Confirm the **test client's effective read-only permissions via configuration**, never by attempting a write. Keep any raw captured receipts outside GitHub.

## Alpha.17 V2-R2 first-answer: lighting attribution transfer (8 November 2026)

A fresh first answer and **private Technical JSON** for the frozen V2-R2 lighting causality question were independently reviewed against the returned native MCP receipts. This is another uncoached `2.0.0-alpha.17` / `gemma4:31b-cloud` single trial, with **zero prior session receipts**. Keep raw household event timestamps, app/device IDs and config payload private, not in this public report.

- **Efficiency:** 15.004 s browser / 14.917 s server, seven model rounds, six native attempts: **five succeeded**, one was a locally rejected live-schema type error on an app-configuration identifier. The model immediately corrected the type without a forwarded invalid call. Three device-event queries returned **24 event rows total** (not a unique-event guarantee), and the focal light's 20-row request reached its requested limit.
- **Verified evidence:** The latest returned OFF **command issuer** was explicit in the native device log; the subsequent OFF **state** was separately reported through its bridge. The configuration identified exactly the two selected motion sensors, inactive-off behaviour and a configured delay. Both sensors' last returned motion events were inactive before the OFF command. The time between the last inactive event and that command matched the configured delay extremely closely. The corresponding motion events listed the controller's **motion event handler as a listener**, not proof that its own timer callback fired.
- **Assessment:** The *inactive-off explanation is strongly supported*, and the answer was useful. However, the model declared the **triggering event**, **causal mechanism**, and **verified cause** certain without retrieving an explicit app-internal schedule/callback/decision trace. Even an exact timing match plus intended configuration and a recorded issuer is not direct proof of the internal branch executed. The state report is bridge-reported, not independent physical actuation verification. Reviewer grade: **PARTIAL (causal certainty overclaim)**.
- **Source boundaries:** App configuration was a contemporaneous read, not a historical settings snapshot. The focal event-history request hit its 20-row limit, so it cannot establish complete older history. No additional read was demonstrably required to support the leading explanation; a discriminating app execution source would be needed to upgrade mechanism certainty. Read-only calls do **not** verify that the effective MCP client is Write denied.
- **Cross-domain learning:** Alpha.17's additional discrete-event gap annotation was present, and an earlier matched humidity comparison showed a narrower improvement in reporting discrete observations. **That improvement did not extend to verified internal automation causality in this lighting case**. This does not establish a broad negative effect or justify a question-specific workaround. Across the three reviewed v2 domains to date, results remain **partial** for different evidence-calibration reasons; do not convert three intentionally selected trials into a general accuracy percentage.

**Engineering decision:** Preserve clean native model-led tool selection. Record the single avoidable schema-type error as an efficiency observation; do not alter the server schema, silently coerce identifiers, block conclusions by keyword or hardcode a delay-to-cause template. Before another runtime patch, compare additional independent domains using the permanent claim-level source/role rubric. The next frozen test is **V2-R4 heating** for complete group membership, historical operating state and setpoint coverage, and command-vs-observation roles. Retain alpha.17, capture an unedited first answer and private Technical JSON, and verify effective read-only grants via client configuration without a write probe.

## Next test and release gate

The installed alpha.17 V2-R2 lighting transfer question has now been source-reviewed: **strong factual correlation, but an overconfident verified internal cause**, with one recoverable schema-type rejection. The frozen **V2-R4 heating** and **V2-R6 offline/stale telemetry** first answers have now been source-reviewed. Both found useful evidence but omitted required scope or promoted correlation to verified causality. The alpha.18 model/runtime remains unchanged. Complete the remaining frozen V2-R1 source-reviewed gate or run a controlled, multi-domain **model-vs-source-presentation** experiment before choosing a general runtime improvement; do not keep adding incident-specific patches or uncoached retries.

Alpha.17 changes only the generic model-visible event-scope annotation and release metadata. It adds **no model prompt, extra model round, router, provider, device rule, recorder, V1 or MCP permission change**. One matched V2-R3 comparison showed narrower discrete-history calibration, while the distinct V2-R2 test still made an unsupported definitive automation-cause claim. Model-wide quality and general transfer remain unverified.

## Installed alpha.17 V2-R4 heating — complete-group first-answer evaluation (8 November 2026)

A fresh, uncoached first answer and private full Technical JSON were reviewed against the returned native MCP source. **No raw household event records, IDs, exact timestamps or private values are committed.**

- **Observed:** 17.575s client / 17.497s server, four model rounds, **10/10 successful native calls**, no schema errors and no prior conversation receipts. The model discovered the main Thermostat and six labelled TRV devices. It retrieved operating-state history for the main thermostat and five room TRVs; the sixth listed TRV exposed no comparable operating-state attribute in the inventory and was not historically queried.
- **Well supported:** The main thermostat reported a recent heating→idle cycle, while four sampled room TRVs reported overlapping heating followed by idle. Its historical setpoint changed at both ends of the main cycle; those changes identified an automation producer. The fifth room TRV's targeted state-history query returned zero records, correctly reported as **unknown**.
- **Missing required coverage:** The model fetched main thermostat historical setpoint/temperature and room-TRV *operating-state* histories, **but never obtained historical setpoint/temperature events for any room TRV**. The zero-row result for the fifth room TRV cannot establish its prior state, and the sixth listed device was not classified explicitly as outside the compared group or lacking the required historical attribute.
- **Unsupported conclusions:** The model converted `thermostatOperatingState=idle` into claims that the **physical radiator valves were closed**, and `thermostatOperatingState=heating` into **the boiler/heat source was firing**. The native responses contained no physical valve-position or boiler-on evidence. Relative onset times suggested possible common scheduler coordination, but did not prove one device triggered another. Main thermostat state/event records are discrete source observations, not an uninterrupted physical-firing trace.
- **Reviewer result: PARTIAL** — useful event alignment, honest disclosure of one empty history and some missing setpoint evidence, but incomplete group/attribute coverage and overconfident physical/causal claims. This is one intentionally selected case, **not** an estimate of model-wide first-answer accuracy. The observed read calls do not prove effective Read allowed / Write denied token policy.

### Decision and subsequent comparison

The weakness is **historical group coverage and source-role interpretation**, not insufficient tool availability. The model itself selected the correct native investigation tools but stopped without the explicitly requested historical TRV setpoints. Retain the native model-led architecture and the unchanged investigation prompt. Do not add a heating-specific planner, fixed call count, blanket claim rewrite or silent state coercion from one case.

The next frozen, independent **V2-R6 offline/stale telemetry** test should examine reporter/lastSeen provenance and alternative causes. Keep its first answer and private Technical JSON, and grade actual evidence rather than tool success. Only after a broader set of reviewed results should a general source-contract or model-comparison experiment be justified.

### Alpha.18 user-interface-only release candidate

The user requested **obvious confirmation when copying the answer**: a static button and status far below long answers were easy to miss. Alpha.18 moves the accessible live copy status adjacent to the Answer header and changes the clicked button to visible success/failure text and styling **only after the clipboard operation returns its outcome**. It resets after a short interval, on a new request, or when a new conversation starts; delayed clipboard completions cannot repaint a later request. Technical JSON content, raw answer text, fallback clipboard handling and tool receipts remain unchanged.

**Expected metric:** reliable, visible user confirmation in the UI, not an increase in model reasoning quality. **Tests:** synthetic JavaScript copy success, failure, expiry, fallback, stale completion and unchanged payload; browser/container CI. **Risk:** timer-dependent visual state may be missed by assistive technology (mitigated by `role=status` and `aria-live=polite`); copy functionality must still work in LAN HTTP fallback. **Rollback:** reinstall alpha.17 / revert the isolated UI and version changes. No Hubitat, Home Assistant or MCP change.

## V2-R6 offline/stale-telemetry source review — installed alpha.18 (8 November 2026)

The user submitted a first-answer Technical JSON from `2.0.0-alpha.18` / the same Gemma cloud model, with zero prior source receipts. Its full raw device records remain private, outside GitHub.

- **Tool efficiency:** 16.554s browser / 16.483s server, four model rounds, **three successful native MCP reads**, no rejected calls. The reads were one device-health snapshot, one bounded hub-events query and one bounded broad past-log query.
- **What was actually returned:** A health classification of **39 stale and 1 unknown out of 211 devices** using a 24-hour `lastActivity` threshold, **not** explicit offline-transition events. The hub event source recorded a firmware update followed by `systemStart`. Several last-activity values were tightly grouped, but occurred **several minutes after** the recorded startup; other stale devices had last activity even later, so the cluster did not establish the most recent actual outage. A couple of last-activity timestamps were before startup.
- **Decisive coverage gap:** The broad past-log call reported **14,816 matching records** but returned **only the latest 100**, all from a short period around the time of the question rather than the previous day's restart. It therefore could not establish that the earlier interval contained no disconnect/error reports. Neither device-specific event histories nor an MQTT connection/session trace were retrieved. `lastActivity` is not a proof of continuous upstream reporting or physical availability.
- **Model strengths:** It found the health snapshot and correlated a real hub update/startup to similar timestamps, avoided declaring all devices physically failed, and acknowledged that MQTT failure and mesh collapse were not directly proven.
- **Unsupported:** It labelled the update/reboot the **verified primary trigger** of the presumed device outage, asserted no offline/disconnect events without checking the relevant log window, interpreted clustered last activity as simultaneous reporting failure, and did not establish the requested **most recent actual offline/unresponsive occasion**. Reboot-before-last-activity is temporal proximity, not a directly observed connectivity-loss mechanism.
- **Reviewer disposition: PARTIAL, with a significant causal and historical-source-coverage failure.** Successful tool calls did not retrieve an actual device-level offline event or relevant MQTT/session/connection evidence. Read-only operations do not prove that the test token's effective Write permission is denied.

### Cross-domain result and next engineering gate

Five intentionally selected, independent domains now have first-answer source reviews: ventilation, humidity, lighting, heating and stale devices. Each was **partial** on claim calibration, group/attribute coverage or absent-source interpretation, despite mainly successful native tools. Alpha.17 improved discrete-history wording in **one** matched humidity comparison, but did not resolve the other domains. This selected sample spans different installed versions and evidence windows; it must **not** be reported as a representative factual accuracy percentage.

A key, general evaluator blind spot was found in R6: the existing offline audit counted device-event source scopes but not returned **native log page coverage**. Extend the **offline audit only** to recognise successful native log receipts and report returned row counts, whether upstream `matched` exceeds returned rows, whether the requested limit was reached, and an explicitly **unknown** completeness/absence-of-errors status. Exclude failed, non-executed and metadata-only responses. Do not include tool arguments, private log messages or timestamps in shareable reports, and never claim missing history because of a page limit. This is **measurement integrity**, not an agent-quality correction or app-version change.

The next discriminating development experiment should compare source-verified claim accuracy across multiple **fixed-source** domains using the same native tool contract. Separate the impact of the model from source-presentation metadata; do not introduce a fixed planner, forced tool sequence, per-device rule, post-hoc answer rewriting or unverified universal claim filters. Treat the remaining frozen reboot case as an independent source-review opportunity, not something to retry until it passes.

## Daily-command first-answer series — native device action and feedback (8 November 2026)

Six **deliberately selected**, user-supervised direct-command exports were reviewed privately from the installed `2.0.0-alpha.18` / same Gemma model. This review spans a scheduler-related thermostat command, basic ON/OFF and two dimmer actions. No raw household labels, IDs, timestamps, text questions, network addresses, MCP payloads or exports are committed. **These are not a representative action-reliability sample.**

| Observed structural outcome | Sample count |
| --- | ---: |
| Native device-command receipts returning accepted | 6 / 6 |
| Commands with a later independent attribute read in the *same response* | 4 / 6 |
| Among those, last reported requested attribute matched | 3 / 4 |
| Among those, last reported requested attribute differed | 1 / 4 |
| Accepted commands without a same-response independent attribute read | 2 / 6 |

Response times ranged **3.970–10.775 seconds**, median **6.252 seconds** (mixed cold/warm conversation context, no population estimate). The 10.775-second ON request spent 4.568s in three device searches, 0.602s on the command and ~5.605s outside measured tools; an identically targeted fresh-conversation ON request instead took **5.684s** with one discovery, one command and one read. A successful read-confirmed OFF request took **3.970s** with two calls. Read-confirmed two-attribute dimmer commands took **6.518s** and **5.985s**; the latter had **zero prior source receipts**.

**Critical source distinctions:**

- A command tool returning `success=true` acknowledges submission/execution at that interface; its embedded state may carry **older timestamps**. It is **not** a post-command independent observation, and should not be scored as achieved physical effect.
- An immediate ON follow-up `hub_get_device_attribute(switch)` returned OFF; a later read and discrete bridge-produced ON event established that the *hub eventually reported ON*. The evidence **does not measure an exact command-to-physical-lamp delay**, prove continuous state, or isolate the command from other possible influences.
- The initial thermostat capability action had an accepted command receipt but no confirmed heater demand/output and bypassed the app's intended coordinated control. Later read-only app investigation found actual form-button controls, but subsequent summaries at times confused scheduled vs emergency targets, assumed writer permissions or claimed freshness despite failed app-config reads. Do not use this history to authorize a heater write.
- The two dimmer cases independently read both target brightness and switch state after the device command, matching the request at that point; actual emitted light and absence of later automation remain unverified.

**Engineering decision:** Keep the successful native model-led `2.0.0-alpha.18` runtime unchanged. Before adding a forced post-action tool call, timer, blocking rule, retry or prompt, make the evidence **measurable** with a privacy-preserving **offline-only action receipt audit**. Its limited generic comparison recognises standard ON/OFF switch requests and `setLevel` level requests **only for descriptive benchmarking**; arbitrary native-app buttons or device commands remain **not comparable** without a typed outcome contract. A later fresh read with a matching value is a *reported attribute observation*, never independently proven physical completion.

### Offline action audit v5 — structural instrumentation, not agent intervention

The local Technical JSON evaluator now distinguishes:
1. Native device-command **attempts** vs accepted echoed **native acknowledgments**.
2. Whether the command response contained embedded (possibly pre-command) state.
3. Successful, **source-ordered, same-device attribute reads** that follow an acknowledged command, and whether at least two different attributes were read.
4. For the small standard command subset only, whether the **last** fresh returned expected attribute value matched or differed, versus not comparable. Multiple consecutive observations are not averaged or treated as a definitive final state.

Exclude failed, locally rejected, non-executed, prior-evidence-only and unrelated-device results. Never export device IDs, source attribute names, values, timestamps, commands, raw arguments or model-generated claims. Keep `physical_effect_and_causality=not_established` and `answer_outcome_claim_quality=human_review_required` regardless of acknowledgments or matches. Tests use synthetic receipts to cover stale embedded state, apparent OFF->ON report, dual-attribute dimmer, false-positive rejection, gateway leaf and privacy.

**Next engineering gate:** source-review the aggregate action audit on the existing **private** exports and compare fixed-source multi-domain model reasoning and evidence presentation. Prefer a generic source-contract improvement only if it transfers across independent domains with no unjustified cost in command latency. Do **not** claim this instrumentation changes user-facing answers, device response or model quality.

## Next gate implemented — blinded fixed-source evidence-presentation benchmark (8 November 2026)

The first controlled comparison scaffold is now implemented **offline only**, without editing the live model or MCP runtime. See docs/HUBITAT-MCP-AI-V2-FIXED-SOURCE-BENCHMARK.md for the exact source-integrity, privacy and manual scoring protocol.

A private inventory of **18 browser Technical JSON exports** found **10 without prior context reported**, containing **52 native attempts**, and **8 with prior evidence**, containing **20 native attempts**. Their medians (12.406s vs 7.813s) are **descriptive only**: question complexity and context differ. The ten eligible exports span both direct actions and investigation evidence; related cases mean that independence and domain balance still require review.

The new fixed_source_benchmark.py prepares counterbalanced A/B *retrospective* review inputs with **byte-preserved recorded MCP response strings** and identical questions/instructions. The only A/B distinction is **generic source-role annotation** alongside the unchanged receipts. Native tool calls, including the user's historical writes, are **never replayed**. The original model answer is omitted from source prompts. Both variants are verified against the same SHA-256; the condition map, raw receipts, answer files, reviewer ratings and identifiers remain in a **private directory outside GitHub**.

The benchmark cannot call a live model, declare an answer correct, grade itself, or verify write permissions. Its report is only paired, blind **human-rated** evidence-grounding, completeness, causal calibration, action-outcome and usefulness comparisons plus descriptive latency. A zero-answer or zero-rated report is **pending**, not a performance result.

**Decision:** Keep the installed v2 runtime at alpha.18. Require a real paired model trial and source review in more than one independent domain before considering a general source-presentation change; preserve command-confirmation safety and response latency. Do not put private exports, transcripts, device IDs, time stamps or secrets in PRs or CI.
