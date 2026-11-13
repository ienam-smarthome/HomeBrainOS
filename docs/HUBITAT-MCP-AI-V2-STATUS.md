# Hubitat MCP AI v2 — architecture and live acceptance

## 13 November 2026 — Alpha.75 source-real control acceptance; return to original model-led reasoning Gate B

**Current repository release: V2 `2.0.0-alpha.75`** (merged PR #1628). A private, installed **first-answer** native delayed-control test reported a successful driver-advertised timed command and a pending deadline; subsequent separate original Hubitat logs reported the deadline fired and a resulting blocked state. A following direct immediate reverse-action request submitted one supported native command and returned source-reported allowed state at its contemporaneous attribute timestamp. These are **two useful action successes**, not evidence of independent physical router enforcement or cross-domain autonomous reasoning accuracy.

**Claim-quality nuance from the immediate reverse action:** the native response's **allowed-state field was freshly updated**, while its pending-timer field had an **earlier** timestamp corresponding to the already-completed timer. The final answer correctly stated that no timer was pending, but did not establish that the new command itself cleared the old timer. Per-attribute freshness, action versus evidence and source chronology remain important.

**PR audit:** #1618 established the model-led native action/outcome review. #1619–1624 experiments were superseded by the explicit rollback #1625. #1626–1628 restored generic alternate-controller discovery and direct-action completion on the alpha.65 native path, with a safety preflight against an unrequested event-triggered rule. These fixes remain limited protective affordances, **not** a fixed tool planner, device-specific mapping or new scheduler. Earlier historical PR notes document superseded features, not current runtime. The accidentally activated event-triggered rule from the earlier test was not altered by the repo and its current status is unverified.

**Priority change:** STOP tuning internet-control commands now. Return to the original **12 fresh, read-only first answers across 6+ domains**, explicit V1/V2 Gate B, source-real causal evidence/claim accuracy, per-attribute timestamps, history pagination and Hub & Device Monitor as independently chosen source. Do not count these two device actions as Gate B causal-investigation samples. Compare model reasoning, evidence coverage, unknowns, tool errors, correctness and latency before writing another general fix. Delayed unblock after a future interval remains a distinct, unimplemented request; existing immediate `allowInternet` is working according to its latest native receipt, and `allowForMinutes` is not delayed-onset allow.

The current plan and source-scoped acceptance gates are in [alpha.75 return-to-original-roadmap decision](HOMEBRAIN-V2-ALPHA75-RETURN-TO-ORIGINAL-GATEB-20261113.md). **No runtime changes are required for this milestone.** Keep V1 and external recorder unchanged.



## 13 November 2026 — Alpha.75: one-off timer is not an unrelated event-driven rule

Source-real alpha.74 request for a delayed TV internet block recovered the alternate native controller but did not inspect the native timing command; instead it offered a temporary rule. After a bare "yes" it created a first **inactive stored draft** (invalid empty mode trigger and seconds=120) and then revised this to an **activated** rule triggered only when mode changes to Afternoon. The screenshot proves the wrong trigger. The original device-native block timer had previously operated, but these later attempts did not schedule it.

Alpha.75 retains the working alpha.65 native timed-command path, alpha.73 generic inventory recovery and alpha.74 model-led follow-through. A successful broad inventory now suffices for a one-time model-led continuation to inspect the alternative actuator, even without a later details receipt. A general authorization preflight prevents rule creation/editing from a direct one-off delay that omitted an independent event trigger or recurring automation; a bare "yes" following an ambiguous assistant proposal cannot manufacture that trigger. The native write is not sent and existing approvals are never bypassed. Explicit genuine rule requests still use the normal upstream approval/backup gates. Original rule storage versus activation and validation errors now appear separately in private Technical JSON.

This is a source-coverage and action-suitability fix, not a new scheduler or a special TV/Cudy branch. **Unintended activated hub rule 4299 remains on the hub and is NOT modified by this code PR.** Pause/delete separately in Hubitat; check any already running waits. Delayed unblock remains a distinct unsupported feature. Synthetic tests are not live installed-model acceptance. [alpha.75 notes](HOMEBRAIN-V2-ALPHA75-ONE-SHOT-TIMER-20261113.md).




## 13 November 2026 — Alpha.74: source-grounded follow-through for native timed commands

Original installed alpha.73 evidence showed the separate managed network controller and `blockInMinutes` command were correctly found, but the model stopped at an unnecessary **after-vs-for** clarification. A later imperative with eight archived receipts ended after **one round, zero current MCP calls**, printing the correct native command as text without dispatch. Neither request created a timer. Separately, native driver logs support a previous 11:55:37 scheduled two-minute block, 11:57:37 enforcement and 12:03:37 later allow; these events do **not** attribute the prior successful timer to either later no-write request.

Alpha.74 retains the alpha.65/72 native delayed-block execution path and alpha.73 inventory recovery. It adds **one bounded model-led original-action completion chance** either (a) when a direct imperative would finish with zero current tool calls despite live native read/write tools being available, or (b) after the model used the broader inventory and successfully inspected a different controller but proposes to stop with no native action. The original model selects further reads and any authorized native command. No default write, device-name exception, automatic retry, Rule Machine or speculative delayed-unblock writer is introduced. The model guidance clarifies **after/in** versus **for** timing and forbids silently reallowing currently blocked devices to manufacture a delayed block. Technical JSON exposes `action_follow_through_invoked`. Installed Gemma first-answer correctness remains **unverified**. See [alpha.74 milestone](HOMEBRAIN-V2-ALPHA74-NATIVE-ACTION-FOLLOWTHROUGH-20261113.md).




## 13 November 2026 — Alpha.73: recover alternate controllers after narrow inventory lookup

The restored alpha.72 live first answer for a natural delayed block stopped after retrieving only the target's media integration, then incorrectly declared the network block unavailable. The previous *separate* alpha.65 successful Google TV delayed block is not evidence that the Nest Hub controller was reliably discovered. The correct problem is incomplete source coverage: label-filtered inventory queries can miss related actuators whose labels, driver capabilities and functional role differ from the media record.

Alpha.73 retains the alpha.65/72 native `blockInMinutes` execution semantics, model-led device selection, and original read-only action/outcome review, with **no** alpha.66–71 action-continuation/receipt rewrites. It adds a single source-real, read-only fallback after a clear device-control imperative stalls **without a native write** following only filtered inventory coverage: the client requests `hub_list_devices(format="context")` with no filters, records the original receipt and provides it as untrusted data for the *model* to choose and verify the correct controller/command. This does not add a device-name patch, automatic write, alternate scheduler, Rule Machine fallback, destructive command or retry. Read-only requests/questions and prior attempted writes are excluded. See [alpha.73 development note](HOMEBRAIN-V2-ALPHA73-CONTROL-SURFACE-INVENTORY-20261113.md).

**Delayed unblock remains a separate unimplemented feature** pending an actual native/Rule Machine writer contract; an immediate temporary allow cannot be called an unblock that begins later. Installed cloud-model first-answer and eventual real network enforcement remain unverified until new live receipts.




## 13 November 2026 — Alpha.72: restore alpha.65 working delayed blocking

**Current runtime:** Reverted to **alpha.65** (`81a81df`) with only packaging labels updated to `2.0.0-alpha.72`. The previously source-real validated Google TV `blockInMinutes(2)` scheduled block and subsequent policy block are the selected historical working baseline. Experimental alpha.66–71 discovery, implementation-feasibility, action-continuation and action-receipt code and associated synthetic tests have been removed. Historical notes for those versions are retained as an archive; their described functionality is **not** present in the restored runtime.

The known separate **delayed unblock** limitation remains. `allowForMinutes` is an immediate allow with finite duration, not an allow that starts after a future delay. No Rule Machine one-time writer, alternative scheduling approach, persistent helper or automatic device write has been added. Code CI and installed live acceptance are distinct. See [alpha.72 rollback/verification plan](HOMEBRAIN-V2-ALPHA72-RESTORE-ALPHA65-20261113.md).




## 13 November 2026 — Alpha.71: pre-dispatch error recovery without double-write or false success

The original alpha.70 installed first-answer capture discovered the correct alternate actuator and its native immediate command. Two command tool attempts then failed **locally** (both 0 ms) because the first lacked a fresh post-continuation `hub_get_device` receipt, while the second encountered the premature one-attempt lock. Hubitat was never called for the action, yet the model replied that the target was unblocked. That is a client action-state and final-grounding defect, not proof the router or Hubitat rejected the command.

Alpha.71 keeps the alpha.70 model-led review/guarded single-device continuation but classifies actual lifecycle boundaries: local preflight rejection (read-only recovery allowed, with bounded corrections); approval denied (no dispatch and no retry); native dispatch and native result (single-attempt rule applies); native timeout (outcome unknown, no retry); and domain-level acceptance separate from any waitFor or native attribute readback. The model still selects any read and the one native command. Original command receipts now carry a `dispatch_state`; Technical JSON exposes source-grounded `action_receipt_status` plus preflight/dispatch counters. A generic final answer guard prevents a model from claiming the command or physical change succeeded when original receipts contradict or cannot support it. Verified native postcondition is still not independent physical/router enforcement.

Fictional tests cover the original preflight/read/correct/dispatch/readback sequence, fail-closed false success reporting, native rejection, accepted-but-unverified state, timeout non-retry, approval denial and nested MCP reply handling. No HomeBrain V1, Hub & Device Monitor or Rule Machine writer changes. **Installed acceptance remains to be validated.** See [alpha.71 development note](HOMEBRAIN-V2-ALPHA71-ACTION-RECEIPTS-20261113.md).




## 13 November 2026 — Alpha.70: general action-goal completion instead of draft-wording gate

In an original alpha.69 live first-answer test, a clear immediate device-action imperative produced two valid reads of the *media* integration. The model ended by asking if the user meant sound, device connectivity or network controls. It did not investigate the separate controller, issue a command or activate any source review. The existing alpha.69 review trigger recognised unsupported-command denials or permission prompts, not **clarification drafts**. The user goal was therefore left unresolved.

Alpha.70 changes the existing review eligibility for explicit imperatives with **no attempted native write** to depend on the original action goal, not the model's draft phrase. The new `action_goal` checkpoint is read-only and model-led, encouraging broader source/actuator discovery and precise identity checks when available evidence does not establish the desired effect. After that review, the existing bounded continuation is offered without a specific phrase trigger, subject to original user intent, a live native device-command writer and sufficient remaining time. It still allows only one single-device command attempt after a **new** exact-device `hub_get_device` command detail, with upstream permissions and approval enforced. No automatic tool selection, fallback scheduler, batch, retry, destructive action or V1 modification. Negative conclusions remain source-bounded and genuine ambiguity can still require user input.

Fictional tests exercise the exact *clarification instead of capability denial* failure shape, successful alternate-controller discovery and one original write plus state readback, no-effect-already/unknown cases, read-only exclusions, fresh detail requirements, and non-retry after a write. **Installed model first-answer quality and real network enforcement remain unverified.** See [alpha.70 development note](HOMEBRAIN-V2-ALPHA70-ACTION-GOAL-20261113.md).




## 13 November 2026 — Alpha.69: complete explicit device actions after alternate-controller discovery

A private alpha.68 first answer for an explicit immediate action correctly found the distinct network-policy actuator during read-only capability discovery but stopped with “Shall I proceed?” despite already having user action intent. It had not retrieved the actuator's actual command details or executed any device command. The optional discovery review was permanently read-only, leaving no path to finish the original permitted ordinary action. An inventory switch=off did not independently verify router enforcement.

Alpha.69 preserves the **read-only discovery review** and adds one model-led **single-device command continuation** only after a clear imperative, a redundant permission question, no prior native write attempts and adequate time. The model must obtain a successful original `hub_get_device` receipt advertising the exact target ID and command; it remains responsible for physical target identity and correct effect mapping. Only `hub_call_device_command` is offered alongside reads, never rule writers or a batch. An attempted late write locks out any further writes, including after a permission failure or ambiguous response; subsequent readback is read-only. Critical/unknown capability records, read-only user requests, questions, ambiguous matches, mandatory confirmations and upstream access gates stay protected. The first native write path outside the optional review is unchanged.

The work is a general answer-to-action completion improvement, not a Cudy or Nest device exception. Tests use entirely fictional integration/actuator IDs and scripted model calls; neither tool availability nor successful router enforcement in a live household is claimed. See [alpha.69 development and acceptance note](HOMEBRAIN-V2-ALPHA69-ACTION-CONTINUATION-20261113.md). Exact-head CI, post-merge CI and installed source-real first-answer checks remain necessary.




## 12 November 2026 — Alpha.68: verify alternative implementation feasibility

A private alpha.67 live first answer correctly found the alternate actuator and its native command list, establishing that the requested delayed start was **not** directly advertised by that device. It nonetheless promised a viable one-time rule, without reading the current rule-writer schema, immediate/dated one-shot trigger contract, persisted delay/action or client authorization. A further filtered inventory was inaccurately described as an exhaustive check of controllers. Missing a native command does not justify a definite assertion that a new rule is feasible or required.

Alpha.68 adds general source-calibration guidance for proposed alternate implementations and reuses the existing one **read-only** model-led review when the model's own draft promises to create/schedule an automation. The LLM may independently inspect live MCP tool definitions using the already available catalog helper and relevant read-only rule/app guides, but cannot create or modify rules or devices during review. A visible writer is not permission to execute; a generic rule reference is not a verified one-time trigger contract. No automatic fallback scheduler, tool routing, extra review pass or V1 change. A fictional scripted test exposes a writer schema and general delay reference but leaves one-time trigger feasibility unknown; additional tests cover absent writer, safety and low-overhead positive read answers.

See [alpha.68 implementation and acceptance note](HOMEBRAIN-V2-ALPHA68-IMPLEMENTATION-FEASIBILITY-20261112.md). Exact-head CI and installed source-real model-led first-answer verification are still required. Real one-time automation creation is NOT claimed.




## 12 November 2026 — Alpha.67: general control-surface discovery after source-bounded denials

Two private alpha.66 first answers inspected named media/speaker integrations but not potential separate controllers for the requested internet-access effect. Successful narrowly label-filtered device inventories were mistakenly treated as complete searches of all possible actuators. One answer concluded a timed action was globally impossible; the other could not identify an alternate internet-control integration. No native tool errors or writes occurred.

Alpha.67 updates general model reasoning about **named physical entity vs requested effect vs real actuator** and the coverage limits of name-filtered inventories. It keeps the model responsible for deciding whether to broaden an actual native inventory or inspect a different controller and verifies shared identity rather than assuming a similar label/IP makes it safe to act. A drafted unsupported-capability verdict can now open one existing **read-only** source sufficiency review with alternate-controller guidance; the review cannot dispatch a new write, retrofit an automation, or silently repair anything. It adds neither a device-specific router nor a mandatory server call, fixed search sequence, separate scheduler or user-facing answer rewrite. The extra text-only final audit is not run for this review.

Fictional regression cases check narrowed inventory then broadened native discovery, cross-record linkage, no-match uncertainty, no gratuitous checkpoint for positive supported reads, and rejection of write attempts during the review. **Live first-answer success remains unverified**, particularly if the model overlooks a controller before its first write or confuses network-identical devices. See [alpha.67 development note](HOMEBRAIN-V2-ALPHA67-CONTROL-SURFACE-DISCOVERY-20261112.md).




## 12 November 2026 — Alpha.66: temporal action intent and truthful nested verification

Private alpha.65 live source evidence confirmed a native delayed action was accepted with a fresh pending deadline, but the same original MCP reply contained `waitFor.timedOut=true` against an unproven “remaining” attribute. The AI omitted this partial failure while reporting successful scheduling. A separate request for an action **after two minutes** used an immediate temporary **for two minutes** command; the returned target state showed access granted immediately, yet the answer did not report the temporal mismatch. No real follow-up action should be inferred from the assistant's earlier wording.

Alpha.66 addresses both as general time/postcondition reasoning: distinguish delayed onset vs temporary duration vs end deadline vs recurrence; choose verification attributes based on documented meaning; expose native nested `waitFor` outcome as a source-bounded annotation to the model and private Technical JSON; prompt the existing read-only action outcome review to report failed optional verification even when command acceptance is supported. No automatic additional tools, retry, scheduler, rule, device-specific guard, corrective write, or change to V1. Synthetic acceptance tests cover immediate-vs-deferred mismatch and independent domain success plus wait timeout. Real installed first-answer effectiveness requires fresh verification.

See [alpha.66 development note](HOMEBRAIN-V2-ALPHA66-POSTCONDITION-FIDELITY-20261112.md).




## 12 November 2026 — Alpha.65: source-grounded action outcomes

A private alpha.64 first answer for a delayed device action selected a similarly named helper switch and got a successful `on` reply, then asserted that a timed downstream action was scheduled. A subsequent read-only investigation found no pending driver timer for the actual target and no matching known automation in bounded checks; this did not exclude every external controller. The failure is model-selected action/outcome conflation rather than a missing client scheduler.

Alpha.65 keeps the clean model-led native tool loop but extends the existing **single evidence sufficiency review** to native potentially state-changing tool results. The model sees its original action receipt and can select existing read-only tools for target/schedule verification. Its review cannot execute any write or retry; no automatic corrective action. Before writing, the skills explicitly compare requested target, outcome and timing with the actual advertised native command and reject names/flags as stand-in proof. The original tool response is not changed; bounded client metadata highlights the call without claiming a downstream effect. An additional tool-free final claim audit does not run for this targeted review, avoiding an extra step known to have sometimes degraded claim calibration. General synthetic action and non-action tests plus release CI required before merge.

This is NOT a guarantee that a cloud model's first selected write will be correct. Install alpha.65 only after checks pass; validate with a new, explicitly permitted, low-risk **live first answer** that includes original tool receipts and native pending-state readback, keeping V1 and external monitoring unchanged. See [alpha.65 development note](HOMEBRAIN-V2-ALPHA65-ACTION-OUTCOME-REVIEW-20261112.md).




## 12 November 2026 — Alpha.64: live catalog and unavailable-tool evidence

After three private model-first permission verification attempts, the latest first answer mistook three local `hub_search_tools` catalog rejections for successful empty search results and falsely claimed a different command was hidden. A best-practice guide mapped write tools to sections but did not prove the current client could execute a write. The issue is general discovery and source-to-claim calibration, not the internet-control driver.

Alpha.64 offers a **model-selected read-only catalog inspector** over the already obtained per-request `tools/list` snapshot. It exposes actual top-level names and direct schemas or server-enumerated gateway leaf candidates, without new MCP calls. Unknown requested tools produce a scoped `unavailable_tool` local error instead of equating a failed search utility with target absence. Models may still choose an advertised gateway's existing read-only `{}` catalog path for its leaf schema. No prompt-specific routing, auto retry, additional model round, host scheduler or source-derived permission grant. Preserve user approval and server gates.

See [alpha.64 development note](HOMEBRAIN-V2-ALPHA64-LIVE-CATALOG-RECOVERY-20261112.md). Fictional tests show the recovery can happen without a write; real installed Gemma first-answer correctness and effective client-write permission remain **unverified**. Next: exact-head CI, install, a fresh unrelated read-only capability-inspection question and original-receipt review.


## 11 November 2026 — Alpha.53 candidate: named, source-scoped home activity

**User-requested UI correction:** "Switches ON" conflated plugs and lights and the overview only returned five example labels per metric. Alpha.53 returns source-scoped **Lights ON** with recognised light names, named active motion sensors, and named low-battery devices including numeric percentages. Positive light classification uses labels, device types and light-specific colour capabilities; generic switches/dimmers alone are not treated as lights. Ambiguous ON switches remain excluded, disclosed as an unclassified count, rather than creating a false full lighting total. Bounded member lists show up to 250 names per metric (every entry for a 210-device inventory), in scrollable compact cards; counts include all qualifying returned entries. Raw device IDs, unrelated inventory and tokens are not exported by the overview.

**Safety/acceptance:** Same read-only `hub_list_devices` or explicitly advertised read gateway, same guarded `/api/overview`, one on load and manual refresh only. No model/agent, Rule Machine, device writes, extra historian, V1 change or automatic polling. Synthetic Python, JS and Chromium tests check false plug/sensor classification, named lists, battery percentages, bounded output, clearing stale names, and no Ask calls. GitHub CI does not verify installed live lighting classification or device freshness. Keep V1/V2 Gate B read-only first-answer comparisons separate.

## 11 November 2026 — Alpha.52 candidate: historical source choice, not device-name routing

**Private paired alpha.51 first-answer investigation (15:17–15:18 UTC):** When the user explicitly named Hub & Device Monitor, the model selected `homebrain_read_device_monitor(mode=history, metric=humidity, range=24h)` and retrieved 287 populated/288 expected saved 5-minute humidity positions, with saved peak 88% at 22:20 10 Nov. However its statement that a shower was running is not proved by humidity alone, and its claimed ≥70% start at 21:55 contradicts the saved 66% bin; first >=70% bin was 22:00. Five-minute bins are not continuous physical observation and sensor freshness was unverified. A nearly identical query not naming the monitor selected only `hub_list_device_events(attribute=humidity, hoursBack=24, limit=100)`; returned 11 events all between 04:56 and 14:22 11 Nov, highest returned 62% at 07:42. Its statement 'humidity remained below 70% over the last 24h' is unsupported because those original receipts did not cover the preceding evening. It acknowledged the older monitor result yet guessed a causal explanation for source differences. Both tool calls succeeded; zero errors. Review based solely on the supplied original receipts: explicit monitor grounding 1/completeness 2/calibration 0/usefulness 1 =4/8; unnamed source grounding 0/completeness 0/calibration 1/usefulness 1 =2/8. Source completeness is assessed against accessible discriminating sources; these are private exposed controls, not held-out A/B proof.

**General development response:** The model must evaluate available historical sources by metric/unit, actual returned coverage, resolution, row limit, provenance/freshness, and known earlier conflicting receipts **without requiring the user to name the historian**. A native query's requested lookback does not prove complete historical coverage. Separate saved-bin extrema cannot establish exact physical threshold times or activities; source preference is not absolute. Update initial model source context, general measurement skill and one model-led historical checkpoint with no forced local tool execution, deterministic source router, extra polling, response rewriting, device-specific case code or actions. Supply fictional synthetic optional-source-choice, unsupported short-window stop and non-historical bypass regression. CI establishes that the mechanism is available, not Gemma choosing it in source-real conditions.

**Acceptance:** Install alpha.52 only once CI is green. In a new conversation, ask a genuinely unseen historical sensor/metric question without naming a recorder; review full private Technical JSON. A second cross-source discrepancy case should distinguish source windows and unknown sensor freshness and avoid unsupported activity attribution. V1 stays stable; next Gate B paired evaluation is unchanged. 
## 11 November 2026 — V1/V2 Gate B: private source-real paired first-answer benchmark

**Installed alpha.51 UI observation:** The user supplied an installed V2 screenshot showing a reconciled native inventory and populated source-scoped Switches ON, Motion active, Low battery and Devices inspected tiles, with external diagnostics online. That is evidence of the overview displaying data, **not** independent confirmation of each device's state or a V1/V2 AI answer comparison. The monitor status line remains "configured; connection not tested" on that page session.

**Next development gate, not another runtime patch:** Implement a strictly OFFLINE, manual-score V1/V2 source-real first-answer comparison pack in docs/HOMEBRAIN-V1-V2-PAIRED-ACCEPTANCE-20261111.md and hubitat-mcp-ai-v2/evaluation/v1_v2_pairs.py. Twelve *new* paired read-only question templates cover system health, hub resource incidents, current states, last-OFF causality, Rule Machine native identity/dated triggers, historical power, two-device comparison, humidity threshold timing and missing history. Prefer identical models/providers, absolute matching windows and fresh conversations; score original receipts separately from answer fluency. A privacy-first local manifest hashes supplied first-answer capture files (SHA-256) and reports only human-entered 0/1/2 scores, pairing comparability, source-review category counts and reported unexpected mutation flags. Incomplete pairs remain unscored, and causal calibration may be N/A only where inapplicable. No model runs, connector calls, Hubitat/HA changes, writing to public repo with private captures or user-visible experiment panels.

**Capability decision:** Preserve V2 alpha.51 as installed baseline; do not build a new system-check engine, author native Rule Machine rules or import V1's host-owned causal patches before unseen paired receipts demonstrate a general, reproducible gap. V1 v0.18.459 remains independently installed and unchanged. The evaluator only tests existing functionality and must not imply the scores were independently verified.

## 11 November 2026 — Alpha.51 candidate: safe home overview informed by V1 side-by-side

The user provided running V2 alpha.50 and V1 0.18.459 screenshots. V2's clean two-tab UI, connected monitor status and diagnostics are working but lack V1's at-a-glance operational state. V1 shows active rooms, lights, motion, low batteries, MCP/provider badges, scheduled system check, external recorder and historical journal. These are different source contracts: do not import V1's system audit, presume all switches are lights, or present missing telemetry as healthy.

**Implemented:** A four-card, source-scoped native Hubitat device overview in V2 Ask: Switches ON, Motion active, Batteries reported below 20%, and Devices inspected. On initial Ask page load, run at most one bounded read-only native MCP inventory request; a Refresh overview button permits further explicit snapshots. Each metric also gives the number of returned devices with that attribute. Declared inventory totals are compared to returned rows; partial/unknown coverage is labelled, never treated as whole-home zero. Missing motion, switch or battery attributes do not imply inactivity, OFF or healthy battery. Counts are not a scheduled system audit and cannot verify freshness of an individual upstream report. The external diagnostics recorder's latest saved status/free OS memory/5m load-equivalent is displayed from existing /api/status without another hub poll.

**Architecture and safety:** Dedicated source-only GET /api/overview with same-origin X-Homebrain-Request guard, strict allowlist of native hub_list_devices flat tool or its explicitly advertised read gateway leaf. No model request, automatic tool selection, device commands, extra permissions, database writes or separate historian. Errors are sanitised; unauthorised requests never contact source. Single read on page open, not recurring polling; manual refresh thereafter. V1 untouched.

**Checks:** Fictional native payloads with dict/list currentStates, partial inventory, malformed/stale attributes, off/on, missing battery, stricter-than-20% alert, gateway permission refusal, failed inventory, source silence, authenticated HTTP, desktop/mobile browser overview and existing Ask/voice/receipt/diagnostic tests. Source-real installed acceptance still required: compare V2 returned count scope with actual Hubitat inventory, not V1's differently classified lights/rooms audit.
## 11 November 2026 — Alpha.50: focused everyday UI and retired experiment surfaces

**Source-real alpha.49 positive control (private user-supplied Technical JSON only):** Gemma queried monitor status and then selected homebrain_read_device_monitor (compare; 12h) for two selected meters, with a shared 01:05–13:05 GMT interval on 11 November. Both calls succeeded, zero tool errors, four model rounds and ~11.04s server time. Extrema match the original summaries; one meter had 95/144 populated, 49 null, 45 held and a longest missing-bin run of 45 minutes; the other had 144/144 populated with no null/held bins. Correctly treated readings as saved-bin values, not uninterrupted physical peaks. No definite cause claimed. Source-based review: grounding 2, completeness 2, usefulness 2, causal N/A — 6/6. One source-real positive case, not a population-level quality claim.

**UI retirement decision:** The daily Experiments (optional) menu and four previously used evaluation panels (AI Benchmark, Autonomous Lab, Reasoning A/B and Real-source A/B) are removed from the Web UI HTML/CSS/JavaScript. Independent backend evaluation modules, test suites and stored study data are deliberately left intact for historical reproducibility. This is a UI-level removal, not silent deletion of historical evidence or changed default AI behaviour.

**Alpha.50 interface:** Modernised responsive dark identity, simplified two-tab navigation (Ask / Chat and Hub Diagnostics), compact question composer with Speak/Ask actions, unobtrusive saved-history connection status and read-only check, answer toolbar, small elapsed/evidence status, collapsible original source/technical details. The original answer text, Copy for review/private JSON, approval controls, conversation evidence, voice and external recorder charts are preserved. Completed question text remains in the composer and Technical JSON instead of repeating again above the answer.

**Validation:** Offline Node and desktop/mobile Chromium tests must verify retired controls absent, Ask/Diagnostics/voice/export/safety intact, and browser rendering responsive; full Python backend experiment tests remain. PR-head/post-merge CI; separately install and visually test. No live Hubitat, Home Assistant, router or V1 changes. Continue held-out paired V1/V2 evaluation, not re-importing retired UI.
## 11 November 2026 — Alpha.49 candidate: aligned historical comparison and V1/V2 capability plan

**Private alpha.48 first-answer review:** The read-only Mini PC versus TV 12-hour comparison correctly selected monitor status/history sources and returned the supported saved 53 W Mini PC high, 0 W first held low and no TV saved values. All 3 monitor calls succeeded; the model cited 53/144 populated Mini PC bins, 91 null bins and 7 held values; 0/144 for TV. It did **not** locate the Mini PC's consecutive missing spans (including one 5h 05m unknown run), and the two independently executed `range=12h` calls differed by nearly one second. Those facts support a general shared-clock comparison operator, not another recorder, device-named patches or post-answer rewriting. Original receipt-based reviewer score 5/6; no independent source-real V1 comparison.

**Alpha.49 candidate:** The optional existing `homebrain_read_device_monitor` exposes `mode=compare` for 2–5 distinct selected monitored IDs. The model chooses whether to invoke it; for relative 1h/6h/12h/24h the host takes one UTC clock snapshot and aligns the common end to the last completed five-minute boundary, then uses the exact SAME `start/end` through separate authenticated monitor custom GETs. For custom mode, preserve the user's exact offset-aware supplied boundaries. Each per-device result includes the source-derived existing interval extrema, report vs held vs null vs absent counts, and bounded lists of consecutive missing/held *bin-position runs* including the longest. The comparison response gives concise summaries, with individual history mode still available for the raw saved bins. Returned-source windows may differ slightly; requested boundaries are identical. A gap in saved-bin values does not prove a physical outage, measured zero or continuous measurement. On any failing source read, stop without fabricating a complete comparison. No poller, native archive change, automatic model tool choice, device action or credential disclosure.

**V1/V2 capability-gap review:** New companion doc `docs/HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md` compares V1 stable add-on code version 0.18.459 with V2 experimental code version alpha.48/49 and establishes staged, held-out acceptance. V1's much broader provider/voice/scheduled audits/Rule Machine host services are code-present, not automatically required or proven configured. V2 keeps the simpler model-led MCP source/receipt design. Preserve the stable V1 add-on unchanged; determine future V2 investments by unseen source-real first-answer tests, read-only parity and safe action confirmation, not feature-count or one exposed benchmark.

**Verification requirement:** Fictional gap-run and one-clock 2-device comparison tests, including exact custom offset, held/null/absent distinctness, 5m alignment, no token leaks, model tool being permitted read-only, and all-or-nothing comparison on source failure. Require exact PR-head pilot/validation/release assurance and four post-merge workflows. Live multi-device model-first improvements and full V1/V2 superiority remain unverified until installation and paired evidence scoring.

## 11 November 2026 — Alpha.48 candidate: window-scoped saved history and provenance clarity

**Private source-real alpha.47 first-answer results (three previously supplied receipts, no independent live recheck):** Hallway temperature correctly retrieved saved 22.2°C maximum and 21.3°C minimum over 144 populated bins, but interpreted every sensor bin as *definitely held/stale*. Bathroom humidity returned 88%RH high, 50%RH low and two missing bins; again treated ambiguous sensor provenance as definitely carried forward. Fridge versus Freezer made four invalid custom-window attempts because it omitted `end`, then retrieved 24-hour reports and tried to answer a 12-hour question; the Fridge's returned 12-hour highest report-containing saved bin was overlooked and 24-hour gap totals were presented as 12-hour statistics. An empty bin, held bin and missing bin position are not interchangeable. The original observations do not identify any physical compressor cause. Baseline scores: 4/6, 5/6 and 2/6 respectively; causal calibration N/A. Two tests had failed parameter-validation attempts, none performed writes.

**Architectural decision:** Do not build a duplicate historian. The authenticated read-only Hub & Device Monitor archive is genuinely accessible and already serves wattage, temperature and humidity. Correct its general history query-summary contract so the model receives source-derived time-scoped statistics rather than manually conflating timestamps, ranges and provenance.

**Alpha.48 implementation:** Keep `homebrain_read_device_monitor` as the model-selected read-only tool. Add `range=12h` by issuing an exact server-side custom-range GET (the upstream monitor does not offer native 12h). Require BOTH start and end for explicit custom reads, with a clear safe error rather than repeated generic ISO timestamp failures. Summarise returned bins only in the requested half-open interval, expose exact returned/requested boundary provenance, filter other-time rows, compute saved-bin extrema for every measurement and separate report-containing saved-bin extrema for power. Distinguish expected time positions, returned non-null saved values, explicitly null rows, *absent positions* and power held-value bins. Retain `coverage_complete=false` and `continuous_physical_peak_verified=false`: even an entirely populated grid does not establish uninterrupted observations. Mark sensor bins `sensor_freshness_unverified` (fresh **or** cached, unknown) and retain the old aggregate field only as a compatibility alias, not proof of stale readings. Preserve monitor-handler timestamp attribution and the existing raw saved-bin list. No automatic extra tool reads, model answer rewriting, new poller, control actions or monitor archive changes.

**Regressions:** Synthetic, non-household tests for reported maxima earlier in window versus lower later reported values, out-of-window maxima excluded, exact 12h vs upstream 24h, fresh/held/unknown classifications, explicit-null vs absent positions, fully populated but not continuous grid, sensor extrema with unknown freshness, duplicate/out-of-order timestamps, and error handling without network requests. Require exact-PR-head pilot/validate/release assurance and post-merge checks; separately install and evaluate uncoached first answers using the original private receipts. CI cannot prove Gemma or the live source improves.

## 11 November 2026 — Alpha.47 candidate: source discovery and historical evidence completeness

**Private alpha.46 first-answer evidence:** Two separately captured uncoached attempts did not use \`homebrain_read_device_monitor\`. A monitor-inventory answer correctly discovered configured device IDs and matching archive filenames, but incorrectly promoted configuration to proof that every selected device had saved measurements. A second answer read only several disjoint 30K-character fragments of a 517,959-character archive, left most offsets unexamined, then stated the requested device had no saved data. Its mixed native-event history contained overnight *amperage* events and late-morning *power* events; the final answer incorrectly combined the overnight times with the late-morning watts. Eight successful native reads per attempt, no reported tool errors, but source completeness and measurement time attribution failed. The receipts did not establish whether the optional monitor API was advertised/configured, and did not verify that the requested device's historical wattage was present or absent.

**Architectural choice:** Reuse the established Hub & Device Monitor historian and its structured, authenticated read-only per-device API before adding another SQLite/MQTT polling store. A second recorder would duplicate measurement collection and would not resolve missing source discovery or unverified archive queries. Keep the eventual separate historian as an option only if source-real archive reachability, performance, retention or fidelity proves insufficient.

**General alpha.47 changes (no incident-specific case logic):**
- Give the normal model a truthful **per-request source catalog**: native read tools present, separately configured monitor-history tool offered or not offered, and that configuration is *not* connectivity or data-coverage proof. Return this as \`available_read_sources\` in ordinary successful Technical JSON so review can distinguish unavailable tool from model selection.
- Add a **manual, read-only monitor connectivity check** to Ask UI. One explicit status GET (no background poll, no token in URL/receipts/UI) reports reachable/configured and number of selected/power-capable devices, but never claims archive coverage.
- Retain original native file-read receipts while attaching conservative **character-range coverage** per successful file chunk and cumulative unique ranges. A filename, a partial JSON excerpt, or \`hasMore: true\` does not establish records are present or absent elsewhere. No source content, tool call, read order or model answer is changed.
- Attach **event-attribute-specific UTC time bounds** for the returned native rows; power timestamp bounds cannot be borrowed from amperage, energy, status or other events. No continuity or arbitrary physical cause inferred from sparse events.
- Extend the single conditional model-led measurement sufficiency review to broad historical **inventory/availability** questions without a specified clock-time interval. Model still chooses sources and may stop calibrated; no forced read, fixed source order, deterministic verdict or automatic rewriting.
- Synthetic tests for source visibility/configuration, explicit status check, original MCP receipt fidelity, incomplete and overlapping file fragments, unit/time segregation, and no device writes.

**Acceptance:** Exact-head CI, merge, post-merge CI. Separately install and verify version. Confirm \`device_monitor.configured\` and use the manual connectivity check; if disabled or unreachable, do not claim the AI selected the wrong tool. With a connected archive, ask an **unseen** historical measurement question for an actually monitored device and examine the \`homebrain_read_device_monitor\` receipt for exact interval, report-vs-held classification, bins and missing intervals. Compare first-answer claims against original receipts; no live verification or quality improvement is established by synthetic CI.

## 11 November 2026 — Alpha.45 installed Ask preflight blocked by stale version response; alpha.46 repair

**Private source-real observation:** The HA add-on card showed alpha.45 and the browser rendered UI alpha.45, while `/api/status.version` reported alpha.44. The preflight rejected the Ask before it reached the model or MCP, so the captured response was null, no native or monitor tools were called, and all answer-quality criteria are **N/A, not attempted**. No command/state cause can be inferred. The repository directly revealed the defect: the FastAPI application and static UI declared alpha.45, but the status endpoint retained a literal alpha.44 version string. This is not evidence of an outdated installed executable or a failed monitor OAuth connection.

**Alpha.46 general repair:** Derive `/api/status.version` from the running FastAPI app's version property instead of a separate hardcoded literal. Bump add-on, runtime and interface to alpha.46 so HA can offer a distinct update, and add an HTTP contract regression proving status/UI/config consistency. Preserve version-mismatch fail-closed behaviour for genuinely stale client/server combinations, all original receipts, read-only monitor tool behavior and unchanged live systems. CI proves the code contract only; subsequent installed-status and source-real measurement retrieval remain unverified.

## 11 November 2026 — Alpha.45 candidate: reuse an existing device historian, read-only

**Finding:** A separate, user-managed Hubitat Hub & Device Monitor Groovy app already saves five-minute power-bin history into daily archive files (plus pending bins), with authenticated read-only \`/api/status\` and \`/api/history\` endpoints. Its graph can show wattage samples even when native \`hub_list_device_events(attribute=power)\` returns no rows. This does NOT show that native history was deleted; it demonstrates two different historical stores. The v1 historical journal's websocket allowlist also does not collect generic numerical power readings, and v2's existing external diagnostics recorder stores hub resources rather than device wattage. Duplicating sampling before using the known archive would add cost without evidence of need.

**Candidate:** Optional, privately configured \`homebrain_read_device_monitor\` local read-only tool in the normal v2 agent. The model may discover monitored IDs/status or independently request a specified historical power/sensor interval. Only the exact authenticated installed-app \`/api/status\` or \`/api/history\` GET endpoint on an explicitly configured RFC1918 IPv4 Hubitat target is permitted; redirects and arbitrary paths/domains are forbidden. URL/token are not visible in model tool arguments, source receipts, status or answers. No Groovy code, monitor archive, device subscription, time-series poller, Hubitat state or MCP server is modified.

**Source fidelity:** Identify saved 5m/hourly bins separately from direct raw reports; preserve report counts, source-report timestamps and bins with held or unknown provenance. A saved wattage bin high/low is not a continuous physical peak, and an unknown bin is not zero. A 30-day daily series's API field named \`w\` actually represents estimated Wh; reject it for instantaneous power. Monitor sensor bins can represent held cached state and are not necessarily fresh sensor samples. The monitor is optional; missing configuration must not disable native MCP Ask.

**Proof and limitations:** Fictional HTTP mocks/agent tests cover status/discovery, model-selected reads during extra evidence review, exact custom UTC boundaries, absence of token leakage, strict fixed LAN endpoint, redirects/errors, report-vs-held classification, and blocking daily energy as power. CI cannot verify installed monitor OAuth/access/actual archive coverage. Separately install verified alpha.45, configure a monitor instance, verify status, then run two uncoached read-only first answers: one with saved wattage bins, one with missing or held bins. Check original source receipts, time-zone conversion, exact source counts, model claims/latency and retention without revealing private OAuth URLs or household data in public notes.

## 11 November 2026 — Alpha.43 private measurement-fidelity failure; alpha.44 candidate

**Private alpha.43 first answer (single historical measurement request, no independent recheck):** Gemma located the intended metered device and correctly issued a narrow time-filtered query for the requested quantity, which returned no matching history rows. It also read mixed history with related but **different units**. The first answer substituted indirect readings and cumulative totals as a historical measurement summary, inferred workload/activity without supporting evidence, and did not clearly state that the requested history was unavailable in the checked source. A later current-state snapshot cannot establish the prior night's measurements. All three MCP reads succeeded; no tool errors; four model rounds; \`source_review_invoked=false\` because alpha.43 only reviewed causal questions. Private reviewer score **2/8** (grounding 1, completeness 1, calibration 0, usefulness 0). This exposed case is not an independent population measure. No original names, IDs, private receipts, or timestamps are committed.

**Engineering finding:** General evidence fidelity has dimensions beyond causal attribution: requested target, physical quantity, unit, historical interval, aggregation and source coverage. A successful exact-filter query with zero rows followed by related nonmatching measurements still does not support the requested series, peaks, device workload or unobserved values.

**Alpha.44 candidate:** Extend the alpha.43 conditional one-time model-led sufficiency checkpoint to broad **historical measurement/data requests**, not specific devices, fixed attributes or unit tables. Before finalising, let the model compare original receipts with the requested metric, unit, target, historical window, sample coverage and intended statistic, then independently select a useful permitted read-only source or state the precise gap. The general first-pass reference also distinguishes current snapshots, indirect measures, cumulative totals and justifiable derived estimates. Do **not** automatically query another source or rewrite an answer. Preserve the causal review and safety gates; add \`source_review_kind\` to normal final results to distinguish causal versus historical measurement reviews. One additional model round has a latency cost, and no improvement is demonstrated merely by CI.

**Blinded-study isolation:** The separate, already-existing two-arm fictional guidance experiment explicitly disables the supplemental checkpoint for both arms, retaining its original comparable first-completion protocol. Normal Ask still reviews eligible historical requests; the experimental opt-out is not a general user bypass.

**Verification/acceptance:** Fictional cross-domain time-scoped retrieval intent tests and model-led synthetic flows cover an empty exact-metric query, related-unit substitution, model-selected archive source, deliberate honest stop, true historical measurements as a positive control, normal current snapshot bypass and read-only enforcement. Require exact-PR-head pilot/validation/release assurance then post-merge checks. Separately install and verify alpha.44 and assess *unseen*, uncoached historical measurement requests with original successful MCP receipts, including one with genuine history and one lacking it. Evaluate correct metric/unit/interval, source coverage, missing data, unjustified estimates and tool choice; measure latency and do not claim real Gemma improvement before that acceptance.

## 11 November 2026 — Alpha.42 live first-answer failure; alpha.43 sufficiency candidate

**Private alpha.42 evaluation (reused case, not independent generalisation):** The model retrieved the correct latest reported state event and its bridge reporter, but incorrectly favoured external initiation without command-origin evidence. Both MCP reads succeeded. The state history was attribute-filtered, so the command-history chronology feature was never exercised. Reviewer score: **2/8** (grounding 1, completeness 0, calibration 0, usefulness 1). Four unpaired alpha.39–42 examples cannot establish a population accuracy trend. No private device names, IDs, timestamps or receipts are published.

**Lifecycle defect:** Alpha.39–42 provided source-derived passive metadata, but the agent returned on the model's first text-only completion. No metadata can help if the discriminating source was never requested.

**Alpha.43 candidate:** An eligible causal completion opens one conditional extra **model-led** evidence-sufficiency deliberation. Gemma examines its successful receipts, filters, source gaps and causal claim, then independently decides whether to choose proportionate read-only MCP sources or stop with a calibrated answer. The client executes no automatic read, retry or fixed tool sequence; it makes no deterministic causal verdict or answer rewrite and changes no write permissions. The API reports a source_review_invoked flag. Extra model latency is a tradeoff; time-short requests retain normal completion. This deliberately revises the earlier no-extra-model-round design, not the prohibition on automatic MCP reads.

**Gate:** Fictional tests for model-chosen follow-up read, model-chosen stop, noncausal bypass and native receipt preservation; CI and post-merge checks; separately installed version verification and genuinely unseen read-only first-answer and positive-control captures. No claim of improved Gemma accuracy before source-real acceptance. No live device or recorder changes.

## 10 November 2026 — Alpha.42 candidate: chronological landmarks without inferred causality

**Private alpha.41 first-answer review (not an overall accuracy rate):** A fresh read-only power-control question led to three successful MCP reads (device lookup, empty 24-hour filtered state query, older unfiltered 50-row event history), no tool errors, four model rounds. The model correctly found a recorded command issuer in the older history, but described a separate OFF-state report as occurring *after* that command when the actual source stamps put the state report almost ten minutes *before* the later command. Later low-power telemetry was separately observed and cannot retroactively establish that the command caused the earlier state report. The 50-row mixed history reached its row limit; app configuration and event-specific callback evidence were not examined. Reviewer score: **3/8** (grounding 1, completeness 1, calibration 0, usefulness 1), one independent sample only. No private device/app names, IDs, event stamps or original receipts are published.

**Generalisable improvement:** Add an optional source-derived, bounded `client_event_chronology` index when a single successful native event-history response contains *both* timestamped command and non-command observations. Show recent returned commands plus earliest/latest returned observations for each event name (up to eight commands and twelve report-name groups), ordered by parsed absolute instants with **original timestamps preserved** and omission counts. Unlike alpha.41's source-role boundary, this exposes recorded ordering to the model without matching a command to an effect, inferring real-world clock synchronization, or asserting a cause. Chronology guidance requires checking absolute source times before calling a command the antecedent of a state report, and treating a command preceding a report as **compatible but not proof**. Original native results, permissions and tool-choice freedom stay intact.

**Fictional tests:** Include a later-command/earlier-state conflict, a positive command-then-state case across differing UTC offsets, many interleaved telemetry names with explicit omitted-landmark counts, unreadable clock values, errors and unchanged agent tool-call/receipt flow. Source-only tests and CI do **not** demonstrate improved real-model chronology or source selection. After installation, use an uncoached, source-real first answer from a new device/automation class and a genuine supported positive control. Preserve uncertainty over clock skew, truncation and gaps. No additional tool round, automatic rereads, device writes, deterministic answer rewrites or incident-specific logic.

## 10 November 2026 — Alpha.41 candidate: distinguish state reports from command-source evidence

**Fresh private alpha.40 first-answer review (not a comparable accuracy estimate):** A new, previously untested lighting-device question returned one device lookup and one successful *attribute-filtered state-history* read. The model identified the latest reported OFF transition and its bridge reporter, but asserted that a `physical` event type excluded an internal app-issued command, offering unverified manual and external control as likely causes. The original two MCP receipts had **zero tool errors**, three model rounds, and **no command-origin history or app execution/configuration reads**; the alpha.40 `client_command_issuer_scope` was never exercised because no command row was returned. Reviewer score: **2/8** (grounding 1, completeness 0, causal calibration 0, usefulness 1). The distinct alpha.39 and alpha.40 examples are **unpaired**; their scores cannot establish a regression. No private device IDs, event timestamps or source receipts are published.

**Generalisable defect:** The model confuses a **state event reporter** with a **command initiator**, and treats a narrow attribute-filtered result as excluding unseen command events. Alpha.41 enhances existing `client_event_source_scope` with distinct requested/upstream-reported attribute filters and explicit bounded counts of returned command, non-command, `physical`-tagged, reporter-bearing and subscriber-bearing rows. Separate source-role fields explain that a report's `producedBy`, `physical` tag or `triggered[]` cannot alone establish manual/external command origin; no command rows in a filter do not establish absence. The original MCP response and alpha.40 issuer map remain intact. Domain-neutral model guidance foregrounds this distinction and consideration of proportionate discriminating read-only sources **before** a causal conclusion, without compelling any particular tool call.

**Safety, limits and acceptance:** No new tool executions, writes, fixed tool chain, mandatory extra model round, answer rewrite, source inference or changed hub/server permissions. Fictional positive and negative controls validate exact source preservation, source-filter provenance, reporter/initiator separation, command-issuer presence where returned and no false actor inferred from filtered state reports. These tests are not real-model evidence. After candidate CI/merge and separate installation, use a **fresh, uncoached, read-only** first answer from a different automation domain; examine original successful receipts and actual additional source selection. Include a real cause-verified positive control when available. Installed version and first-answer improvement remain unverified until independently captured.

## 10 November 2026 — Alpha.40 candidate: source-derived command-issuer handoff

**Fresh private alpha.39 first-answer review (not a population score):** A new historical controller investigation retrieved the device and two event-history views, correctly identified a setpoint-command issuer and chronological state reports, then called a particular internal scheduling mechanism "almost certainly" responsible based on the actor's name and clock alignment. It made **three successful read calls, four model rounds and no tool errors**, but did **not** request a controller configuration page or execution log. The alpha.39 configuration source map was therefore never generated. Reviewer score: **3/8** (grounding 1, completeness 1, calibration 0, usefulness 1). No private labels, IDs, timestamps or source payloads are published here.

**General engineering finding:** Across independent controller domains, identifying the command issuer is not the same as establishing *why* the issuer acted. A passive configuration sidecar can only help after the model selects a config read. The new alpha.40 candidate adds a **bounded, source-derived `client_command_issuer_scope`** to successful native event responses containing returned command rows. It indexes the command's own name, source timestamp and `producedBy` actor (up to 12 examples, with an omission count), and states exactly what the issuer field does **not** establish. It does not infer scheduled callbacks, choose a controller, inspect other pages or override original source data. Model guidance now makes the issuer-to-internal-decision handoff explicit and discourages guessing a schedule from clock time or an app name.

**Safety and evaluation:** Existing native MCP content, per-client server permissions, actual read/write calls, manual approvals, source-scope metadata and model-selected tool sequence remain intact. No command or configuration read is automatically injected. Fictional regression tests verify exact source preservation, actor vs state reporter, bounded examples, omitted or unknown issuer, error/non-command exclusion and visibility during the normal agent loop. Passing these tests does **not** demonstrate that Gemma will choose missing discriminating reads. First-answer acceptance requires a new uncoached read-only event from a different domain, plus a genuinely supported positive control, scored against original successful receipts. The installed add-on version remains unverified.

## 10 November 2026 — Alpha.39 candidate: general causal-source completeness from config pages

**Evidence motivating the change:** Two private first-answer investigations in different controller domains correctly established command issuers and produced coherent timing-based candidate explanations, but asserted the exact internal trigger while compatible alternative paths remained. One omitted a separate required input and a backup timer; the other ignored additional humidity inputs, input freshness and a manual-run path with the same duration as the scheduled run. These observations were collected through the normal Ask flow and are **not** population-level accuracy measurements. The private household receipts and identifiers are not committed.

**General implementation:** Add a bounded, source-derived `client_config_source_map` alongside the native MCP payload for successfully returned installed-app config pages. It indexes **one page actually read**: links to other pages, selected input groups, returned scalar values and explicit omission counts. It cannot prove historic settings or a specific timer/callback. The normal model-led agent decides what to read next. Extend the general causal skill to compare materially compatible mechanisms, participating input freshness/coverage and discriminating event-specific callback records. No special cases, deterministic causal verifier, mandatory extra tool round, output rewriting, write automation or changed permissions. Original MCP text, errors and evidence receipts remain intact.

**Acceptance boundary:** Synthetic tests establish only the metadata construction, source fidelity and unchanged model-owned tool choices; they cannot establish Gemma's first-answer quality. After merging and separately installing, capture a fresh uncoached read-only investigation from another controller class. Score grounding, source completeness, causal calibration and usefulness 0/1/2 against the actual successful receipts. Include a genuine positive-control trace when available so the model can still state verified causes confidently. Neither a present-day settings page nor copied metadata alone proves the historical internal trigger.


## 10 November 2026 — Alpha.38 first-answer finding: competing causal paths not distinguished

**Private first-answer review:** One alpha.38 response to a newly captured lighting-controller question correctly identified the reported state transition, the exact preceding OFF-command issuer, the relevant app's current configuration and a motion event whose timing was compatible with an inactive-delay rule. The four original MCP read receipts succeeded; there were no local schema failures. **This does not test alpha.38's new contract-recovery capability.** First-answer quality was assessed as **3/8** (grounding 1, completeness 1, calibration 0, usefulness 1); this is a reviewer score for one exposed example, not a general model accuracy statistic.

**Newly identified competing explanation:** The same OFF command also occurred close to a second, separately configured backup-off interval following the most recent reported ON state. The returned evidence therefore supports **at least two timing-compatible candidate control paths**. The model declared the inactivity trigger verified without establishing the state of **every configured participating motion input** or reading event-specific application execution/timer logs. A current app configuration confirms available paths, not which timer actually fired or whether that config was identical at the historical moment.

**General issue:** Event chronology can be accurate while *causal path selection* is not. A close time match is not necessarily unique. Before making a definitive source-to-outcome claim, compare materially competing configured paths and ask what **discriminating observations** would separate them. Neither `producedBy` nor `triggered[]` on a physical event substitutes for internal execution receipts. Unread sensors and missing logs are unknown, not proof they were inactive or irrelevant. Do not mistake a successful-but-narrow MCP read for full investigation coverage.

**Development decision:** No runtime edits, device-specific answer rules, deterministic routing, mandatory second investigation, or changed permissions for this exposed case. Record as a cross-domain causal-sufficiency finding and run a **fresh, uncoached, read-only investigation of a different controller class** before considering a general model/tool-schema improvement. Keep household events, IDs, raw settings, tokens and source receipts private; CI does not establish the installed version or live causal accuracy.


## 10 November 2026 — Alpha.38 candidate: model-directed live-schema error recovery

**Motivation:** A recent private first-answer historical heating investigation retrieved a device transition and a controller setpoint command, but failed to obtain important controller configuration because a selected MCP read passed an argument of the wrong JSON type. The rejected request was correctly marked as an unexecuted contract error; the model did not recover its critical read. Other evidence limits remain: contemporaneous sensor and execution trace were not fully available, and a current or later snapshot alone does not verify a historic triggering condition. Private source receipts, device names and event timestamps are intentionally **not** copied into public GitHub notes.

**General implementation:** Return a *bounded, redacted, server-origin* `live_input_contract` with locally rejected MCP calls, including exact declared type of the implicated parameter for direct tools or discovered gateway leaves. The normal model decides whether to issue a corrected **read**; no additional obligatory model turn, auto-tool retry, workaround writer, inferred confirmation or incident-specific route. Always retain the failed `contract_error` receipt with `operation_executed=false`; never apply that status to transport/server errors of uncertain execution. Updated causal skill treats a failed necessary read as **unavailable evidence**, not checked settings.

**Acceptance:** CI/synthetic tests exercise a fake direct read, gateway leaf, intentionally invalid action, bounded/redacted catalog excerpt and original source fidelity. Passing CI establishes code integration only; a fresh installed first-answer investigation must establish whether Gemma itself actually recovers and whether its conclusion is calibrated. No change to Hubitat/Home Assistant, backups, network or recorder.


## 10 November 2026 — Alpha.37 release accepted by CI; next source-selection checkpoint

**Repository verification:** `main` commit `ee7cb71d00d17d47979349bb504567a4d93da2c2` (v2 `2.0.0-alpha.37`), with four passing post-merge workflows. Alpha.37 improves visible British-format answer dates (GMT/BST) while preserving private original MCP and answer text. **No independent installed Home Assistant build or model-compliance check has been completed.**

**Quality observation from a private, previously exposed alpha.36 first answer:** The model located a focal device OFF-state event and distinguished an event subscriber from an initiator, but treated a filtered *state-history* read as relevant to the absence of an OFF command, relied on connectivity results sampled much later, and viewed an app's root configuration without independently establishing event-specific unit settings or decision logs. The private device labels, timestamps, receipts and identifiers are intentionally excluded from GitHub.

**General failure class:** The model needs to inspect the semantics of the source it has actually queried: attribute/event filter, limit and lookback, exact overlap with the focal event, config page/child scope, and whether the returned data could discriminate among alternative causes. All successful tool calls are not the same as sufficient evidence. A later successful diagnostic sample does not establish an earlier condition. This follows existing source-scope and negative-evidence guidance; **do not add another incident-specific prompt patch based on one newly reviewed answer**.

**Next action:** Obtain an independent, fresh read-only first answer in a distinct historical controller domain, using a new conversation with the installed build/version recorded and a private `Copy for review` packet. Evaluate original successful receipts on chronology, filters, command issuer versus reporter, source completeness, historical-versus-current configuration and causal calibration (0/1/2 per dimension). If source-scope mistakes recur across domains, assess a general tool-schema/source-intent improvement without fixed tool routes, increased mandatory rounds, source rewrites or household-specific code.


## 10 November 2026 — Alpha.36 candidate: cross-domain negative-evidence calibration

**Why:** Recent user-supplied first-answer receipts across unrelated lighting-controller and power-telemetry questions showed that a model can correctly retrieve observations yet make unjustified *negative* conclusions (for example, interpreting lack of a returned command row or a successful later report as proof that no interruption occurred). Those original private receipts remain **outside the repository**. This is a clustered evidence-quality failure, not measured model improvement, and a few exposed first answers cannot estimate population accuracy.

**Change:** Extend the existing model-loaded domain-neutral causal skill to distinguish point observations, bounded event lookbacks and interval-continuity claims; apply a counterexample check to definitive absence language; identify relevant but proportionate independent read-only sources when available; and preserve confident answers where execution/trigger/outcome sources actually establish a specific cause. No device-specific patches, fixed investigative tool chain, automatic extra round, output rewriting, source mutation, or added device permissions. Synthetic tests cover model prompt delivery, untouched original event-source coverage metadata and no extra MCP calls, plus a fictional confident positive control.

**Release gate:** Required GitHub workflows must pass before merge. CI cannot demonstrate that a particular cloud model applied the instruction, or prove a real supply never failed. Installed acceptance requires fresh first-answer captures from *different* domains (including at least one genuine verified cause). Compare against original successful MCP receipts using 0/1/2 grounding, completeness, causal calibration and usefulness ratings. Do not repeat one exposed incident as an independent benchmark. The currently installed add-on version has not been independently verified.


## 10 November 2026 — Alpha.35 installed-acceptance and next reasoning milestone

**Repository state (verified):** `main` at `68729a1cd71d0320ddf71396c057e860bb217f44`, add-on manifest `2.0.0-alpha.35`. PR #1577 added an optional taller two-panel incident timeline, including three user-selectable source pairs, independent Y-axis scales and preserved full-page selection/zoom; PR #1578 repaired a race in the unrelated synthetic reasoning browser acceptance. All four main-branch workflows completed successfully for that SHA. **The installed add-on version and actual plotted Home Assistant recorder data have not been independently verified.** Green CI is not proof of installed correctness.

**Evidence-quality development status:** Alpha.33 introduced general model-led causal timing/alternatives guidance. The user-supplied first answers on controller command attribution and ventilation were informative but did not prove that internal automation triggers were correctly identified. The recent chart layout releases alpha.34/35 are presentation/source-coverage changes, **not model-quality improvements**. Avoid attributing a population-level reasoning score to the small exposed examples.

**Next milestone:** Prioritise fresh read-only, first-answer trials across unrelated device domains before further modifying the production prompt/agent loop. Review the original successful MCP receipts for exact chronology, lookback boundaries, command issuer versus event reporter, current settings versus historical settings, alternative mechanisms and the earliest genuinely discriminating evidence. Capture whether the model compared a predicted *sequence* (start, state, duration, stop) against observations—not merely whether timestamps coincided. Missing source rows and present-day attributes do not prove historical absence or continuous state. Keep each first answer uncoached, in a fresh conversation; apply 0/1/2 grounding, source completeness, causal calibration and usefulness scoring only against retrieved original receipts. Testing and grading remain human-supervised.

**Engineering gate:** Cluster at least two materially distinct general failures before considering a new production causal instruction or runtime mechanism. A positive control with a genuinely supported event-specific cause is also valuable: the model should state evidence-supported causes confidently, rather than reflexively abstaining. Make any subsequent fix domain-neutral, model-led, read-only by default for diagnostic tests, and validate with fictional contract tests plus a new live first-answer capture. Avoid case-specific device patches and do not expose household receipts in GitHub.

See `docs/HUBITAT-MCP-AI-V2-NEXT-MILESTONE.md` and `docs/HUBITAT-MCP-AI-V2-LIVE-REVIEW-WORKFLOW.md` for the test protocol.


## 10 November 2026 — Alpha.31: native memory reconciliation candidate

The 9 Nov 21:55–22:57 screenshots showed Hub & Device Monitor reporting a native free OS memory peak near 22:20 (1,272.8 MB) not visible in the HomeBrain external-probe memory timeline. Source review identified the structural omission: the recorder read the *last* native five-minute CSV row only and the unified timeline omitted native OS-memory history. This does not prove that the original 22:20 row remains available.

The candidate separately saves every available timestamped native CSV row under an original-label unique key, retains its source-time and collection-time provenance, displays native OS memory beside independent external memory in the unified graph, and exposes a native five-minute memory metric for detailed history. Unresolvable timestamps are not fabricated. Pre-upgrade cached readings remain an explicitly designated collector-time fallback. A configurable hub time zone (Europe/London by default) is used to interpret yearless native labels. No missing measurements are interpolated, and no timeline alignment establishes causation.

Regression fixtures cover a 1,272.8 MB peak backfilled from CSV, duplicate labels, collector replays, persisted records, source timezone conversion and browser inspection. CI is not evidence that the specific 9 Nov native record was recovered; installed-HomeBrainOS acceptance remains pending. All changes are read-only and isolated to v2 diagnostics.


Updated: 2026-11-10
**Current repository version:** Consult `hubitat-mcp-ai-v2/config.yaml` on `main` and the latest milestone at the end of this document. Alpha.25 was merged via PR #1560; alpha.26 blind-rating integrity was merged via PR #1561 (merge SHA `cf23106d7309c43bf2d71533159a6533cce13f4f`). A GitHub merge is not proof that the version has been installed in Home Assistant. **Installed v2 version is not verified for alpha.25/alpha.26.**
**Historical acceptance:** The last cited private V2-R6 Technical JSON verified the UI as alpha.18 with unchanged Gemma/native flat model path; browser copy-button visual acceptance remains unverified. V2-R3, R2, R4, R5 and R6 source reviews are retained below. PR #1542 merged as `4e486befbc2cd996b6c9eaf635229efee94a0351` (evaluation-only checkpoint).

## 10 November 2026 — Alpha.29: day-to-day Ask and fast review UX

User-directed pivot from mandatory blinded A/B loops to ordinary live Ask questions with optional Technical JSON review here. The UI adds browser-local **Copy for review**, collapses the four experiments under a menu and reduces Ask form space. MCP model/tool loop, token permission, action approvals, native rule handling, Hub Diagnostics and existing studies remain unchanged. Private evidence stays local unless explicitly shared. No measured answer-quality improvement is claimed from this UI change. See `docs/HUBITAT-MCP-AI-V2-LIVE-REVIEW-WORKFLOW.md`. Installed-version acceptance remains unverified.

## 10 November 2026 — Alpha.28: structured causal-review gate and source-response parity

The prior alpha.27 two-case study failed to demonstrate improved factual grounding or source completeness from the experimental generic source ledger, and had **no applicable causal-calibration grades**. The next milestone therefore instruments a prospective **causality-first review**, not a new agent prompt or intervention. New alpha.28 adds a causality-specific freeze mode (4–10 independently prechecked targets with explicit operator attestation), private per-arm definite causal assertion review (`supported` / `unsupported` / `unverified` with original receipt indices), mandatory 0/1/2 causal-calibration scoring even when the model appropriately abstains, and receipt-set comparison to expose same-call payload differences and unmatched reads. An unsupported definite causal claim cannot be given a fully supported causal-calibration score. The privacy-safe final report counts reviewed claim verdicts and source comparability but never exports claim texts, private names, source payloads or hashes.

**Strict boundaries:** The operator's target validation and claim truth are still **manual attestations**, never independent proof; same-response comparisons do not establish complete source windows or physical causation. The existing per-client Read ON / Write OFF permission gate and server-defined read-only native tool filter remain unchanged before each A/B arm. **No model, hub or cloud calls are triggered by developing or enabling the feature.** Normal production `Agent` and ordinary Ask/Chat remain unchanged, v1 and Hub Diagnostics untouched, the source-ledger candidate still **not promoted**. The existing `new-01/02`, `sr-..` and fictional holdouts are now exposed and must not be included in a new unseen set. The alpha.28 release and actual installed version are separate facts; live causality evaluation is **not yet measured**. See [new causal-review runbook](HUBITAT-MCP-AI-V2-CAUSAL-REVIEW-READINESS.md).

## 10 November 2026 — First prospective source-ledger A/B pair study completed: no promotion

Two newly frozen real-source alpha.27 A/B pairs (`new-01` and `new-02`) have now been completed, blind-scored and unblinded. The generic source-ledger candidate performed **worse** than unchanged Agent on factual grounding **2/4 vs baseline 3/4** and source completeness **2/4 vs baseline 3/4**, while scoring higher on usefulness **3/4 vs baseline 2/4**. The candidate used **6** model-selected MCP attempts vs baseline **5**, with **1** reported failure each; its paired median response time was **462 ms slower**. **Causal calibration was not rated** for either question (0 applicable pairs), and the report does not independently verify model accuracy, identical live source snapshots or token enforcement.

Case-level analysis: both variants miscounted device voltage attributes in `new-01`, despite the baseline better distinguishing full device identity inventory from authorized currentStates coverage; both largely grounded app status correctly in `new-02`, where candidate's more exact counts increased usefulness. This is a **two-question exploratory outcome only**, not a general performance estimate. **Do not promote the candidate or repeat these exposed questions as unseen validation.** Keep normal Ask on the original model-led Agent; focus future study on causality, evidence sufficiency and independently verified source aggregation across a fresh unseen set. Details: [two-pair study results](HUBITAT-MCP-AI-V2-SOURCE-LEDGER-PILOT-RESULTS.md). No MCP device, HA or repository runtime changes were made by this documentation update.

## 10 November 2026 — Alpha.27 prospective source-real A/B runner (explicit opt-in)

The earlier alpha.26 production agent and opt-in collection-ledger candidate were structurally verified but the candidate was **not measured on new source-real first answers**. Alpha.27 now adds a separate **Real-source A/B** tab and routes, using the same model-selected native MCP loop for both arms, with the existing production Agent as baseline and SourceLedgerExperimentalAgent as candidate. The normal Ask path remains unchanged. The model chooses its own read-only tool sequence, and the candidate changes only how returned inventory/log metadata is presented. The user freezes 2–10 new private questions before any run, and A/B assignments remain hidden until every pair is manually scored. Question/response evidence resides in **memory only**, not the Git repository or long-lived add-on data. No frozen old holdout or ten exposed first-answer question can be counted as newly unseen.

**Non-negotiable preflight:** each experiment arm requires a newly retrieved native hub_get_info response under the configured v2 token containing **clientAccess.readEnabled:true** and **clientAccess.writeEnabled:false**, with the global read master on. The global Write master alone is not a per-client grant. Direct/gateway tool catalogs are filtered by the upstream server's explicit **annotations.readOnlyHint=true**; selected gateway leaves must be independently marked read-only. Unknown classifications fail closed. The app performs no write probe or device control. The run endpoint requires **explicit model, private-source and cloud/remote-transfer consent** as applicable; running two independent first answers can consume model credits. The API and UI never initiate runs in the background automatically.

This is an operational **evaluation interface**, not successful measured AI reasoning. Structural CI uses fictional sources and fake models only. Because the arms query real sources sequentially, source-state drift is possible and must be assessed before comparing claims. Manual blinded scoring and evidence-ground-truth verification remain outstanding. The origin of the new question bank and exact target capability must be checked independently. Keep developer guidance model-led and avoid per-question prompts, fixed tools or inference round quotas. A new deployed alpha.27 must be installed/restarted before the test tab exists; a GitHub merge alone is not an installed version confirmation. See [prospective A/B runbook](HUBITAT-MCP-AI-V2-PROSPECTIVE-SOURCE-AB.md).

## 9 November 2026 — Generic source-collection ledger prototype (not production-enabled)

The next general reasoning candidate is an **opt-in experimental result-presentation variant**, not another incident-specific prompt. The normal v2 `Agent` still presents native results with the preexisting event-history source-scope metadata only; its behavior is unchanged. The new `SourceLedgerExperimentalAgent` adds generic **returned-row count**, **upstream matched/total**, **requested source filter**, **partial-page** and **currentStates field coverage within returned device rows** metadata to read results when they contain an unambiguous device/app/log collection. Original native results remain intact; no forced tools, fixed plans, automatic retries, answer rewriting, additional model rounds or permission changes occur.

This directly targets the general source-shape class revealed in the exposed baseline, but cannot claim it improves correctness. Structural unit tests use wholly fictional records, assess payload preservation and no added MCP calls, and explicitly do not rate AI answer quality. The previously tested 6 fictional holdouts and 10 source-real captures are **known to development** and must not be used as a fresh evaluation. The detailed [experimental specification](HUBITAT-MCP-AI-V2-EXPERIMENTAL-SOURCE-LEDGER.md) requires a **new, blinded, independently source-verified, server-read-only** evaluation on unseen questions before any production promotion. Installed v2 remains alpha.26 and no new live MCP or cloud model calls have been made as part of this prototype.

## 9 November 2026 — Master Write vs client-token Write correctly distinguished

The source-real capture verifier now reports a **privacy-safe permission-evidence section** from successful native `hub_get_info` MCP receipts: `global_write_enabled_reported`, `per_client_write_enabled_reported` (null when `clientAccess` is missing), client count, and explicit status. It does **not** leak the hub IP, client name, URLs, token, tool descriptions or raw payload. It never attempts a write and it deliberately leaves `read_only_permission_independently_verified: false`, since source flags alone cannot independently test enforcement.

Crucial upstream contract: top-level `hub_get_info.writeEnabled` is the global `settings.enableWrite` master (ON by default), **not** the connected client's write grant. Only `hub_get_info.clientAccess.writeEnabled` (available with a recognised per-client access token) reports the client's grant. The first supplied `sr-01` source reported global Write true and **no `clientAccess` field**, so per-client Write is **unknown, not proven true**. To narrow v2 evaluation safely while retaining other clients, use Hubitat **Apps → MCP Rule Server → Settings → Advanced → Per-client access tokens**, assign a dedicated evaluation client **Read ON, Write OFF**, configure its URL/token privately in v2, then verify the fresh read-only `hub_get_info` includes `clientAccess.writeEnabled: false`. Refer to [source-real capture and access instructions](HUBITAT-MCP-AI-V2-SOURCE-REAL-CAPTURE.md). No live MCP call or token change was made by the repository work.

## 9 November 2026 — First ten source-real Ask receipts reviewed (provisional)

The user supplied all **ten new first-answer Technical JSON exports** for source-real acceptance. They report add-on **2.0.0-alpha.26**, the same cloud model, ten successful API responses, **21 native tool attempts** (20 successful, one server-reported error), **29 model rounds**, no prior-receipt use and **zero device-control calls**. These are real-hub-source exports as supplied by the user, not a witnessed run or independent hub query. The local frozen manifest/SHA was **not provided**, and `hub_get_info` reported `writeEnabled:true`, so **server-enforced read-only access is unverified** despite zero observed writes.

Receipt review: **four source-supported answers**, **four partial/qualified cases** (one used a motion-only sensor instead of the intended contact sensor), and **two material errors**. Material errors: inaccurate battery-field inventory totals (**32 present / 179 missing** in 211 returned vs answer's 22/189) and diagnostics source-scope overreach (only **100 WARN rows out of 124 WARN matches**, without separately checking ERROR, plus unproved reboot-effect attribution). Other gaps include default 24-hour historical lookback for a latest-N request, firmware-update causality overstated, and silent replacement of an unmatched app with a related controller. This is a **preliminary transcript-supported classification**, not independently graded claim-level ground truth or a measured model quality rate. No synthetic candidate promotion or production code change follows.

Details, custody, permission/integrity limitations and the prospective study gate: [source-real receipt results](HUBITAT-MCP-AI-V2-SOURCE-REAL-RESULTS.md). The ten cases are now **exposed** and must not be reused as an independent unseen test after tuning. Next: independently verify a server-enforced read-only token, validate the original local sealed study packet, conduct source-level factual review and design a genuinely *new* held-out prospective comparison of any **general** model-led reasoning enhancement. Keep v1, Hub Diagnostics and v2 production guidance unchanged.

## 9 November 2026 — Next milestone phase 2: sealed real-source capture pack

Proceeding from the completed Phase 1 privacy-preserving human-review auditor, the new offline `tools/source_real_acceptance.py` utility freezes **ten new, previously ungraded, read-only question definitions** with private user-chosen labels. It writes the SHA-256-sealed manifest locally, requires one exact-question first Technical JSON per case from the installed v2 Ask UI and verifies question integrity, duplicate requests, carried conversation evidence, reported command attempts and build/model consistency. It reuses the existing offline evidence auditor and human-review overlay; no native MCP, HA, Ollama, device or cloud call is made by the tool.

Source-real collection is **not yet executed**; no factual grounding or causal acceptance rate is established by these preparatory tests. The operator must use a server-enforced read-only MCP token if/when running the frozen questions in v2 Ask and keep all private records out of the repository. The pack includes no result answer key; a later separate reviewer inspects source reality. The earlier six synthetic A/B holdouts stay frozen and revealed. See [capture runbook](HUBITAT-MCP-AI-V2-SOURCE-REAL-CAPTURE.md). No production agent prompt, routing, controller actions, v1 or Hub Diagnostics changes; version stays at alpha.26.

## 9 November 2026 — Next milestone phase 1: private source-real quality review

After reviewing the unblinded six-case A/B findings, the next step is **not** promotion of the candidate prompt. The critical unresolved problem is deciding which discriminating source to retrieve and using the upstream MCP schema correctly; candidate and baseline tied on causal calibration (7/12) and required-source checks (10/23).

This phase extends the existing **offline** `hubitat-mcp-ai-v2/tools/first_answer_audit.py` with an opt-in, separately supplied private human-review overlay. It preserves original first-answer Technical JSON exports and never grades answer correctness from tool counts alone. Only human-attested **real, first-attempt** samples can contribute to factual grounding, definitive unsupported causal-claim counts, usefulness and source-sufficiency denominators. Non-first, fictional and unknown-source reviews are explicitly excluded; zero reviewed claims leave the relevant rate/count null. The private reviewer data is not copied into the safe summary, and reviewer/source attestations are not independently verified by the script. Tests use fake exports. This is measurement tooling **only**, not any inference or live MCP behaviour change.

The next steps are to capture a **new unseen source-real** read-only first-answer set, independently review exact receipts, diagnose missing source classes/invalid schema calls/causal overclaims and **then** evaluate one general model-led intervention prospectively against unchanged production. Keep the six revealed `hold-..` experiments frozen. The full approach, private CLI review schema, targets and boundaries are in [v2 next milestone](HUBITAT-MCP-AI-V2-NEXT-MILESTONE.md). Version remains unchanged for this offline tooling/docs milestone. No HA/hub access or cloud inference was used to create these notes.

## 9 November 2026 — Completed alpha.25/26 blinded synthetic reasoning holdout

The user supplied a final six-case A/B report with **6/6 model pairs completed, 6/6 blind ratings entered, mapping revealed**, and zero live MCP calls/device actions. Experimental generic investigation-audit candidate vs production baseline: **36/50 (72%) vs 31/50 (62%)** manually rated points, four candidate wins and two baseline wins. Factual grounding **10/12 vs 7/12** and manual source completeness **7/12 vs 5/12** favored candidate, but the **primary causal calibration remained 7/12 vs 7/12**; usefulness **10/12 vs 10/12**, command outcome **2/2 vs 2/2**, and exact source-check retrieval **10/23 vs 10/23** also tied. Tool attempts 30 vs 35, schema errors 4 vs 3, total synthetic elapsed time 33.165s vs 31.045s (candidate vs baseline). Single evaluator ratings were ChatGPT-informed, sample is tiny/fictional, and the export does not establish the installed add-on SHA or configured model provider. See [the frozen detailed evaluation](HUBITAT-MCP-AI-V2-REASONING-HOLDOUT.md).

**Decision:** The candidate is **not promoted**; its slight aggregate score improvement did not improve causal calibration or discriminating-source retrieval. Preserve the existing production model-led loop, upstream permissions, diagnostics, and v1. Next milestone is independent unseen, read-only, source-verified cross-domain first-answer acceptance and a prospective, general tool-schema/evidence-sufficiency experiment only if warranted. Do not patch these six revealed holdout cases or claim general reliability from them. No live operations or cloud runs occurred as part of this documentation update.

## Current user direction

V2 is a clean, model-led client for the upstream Hubitat MCP server's intended capabilities: investigation, device control, automation authoring and administration according to the connected server/token permissions. Do not reintroduce v1 planners, incident-specific fixes, answer rewriting, fixed round quotas or a HomeBrain-maintained tool inventory. V1 remains separate.

This supersedes the earlier read-only-pilot architecture and alpha.2 frozen allowlist. A read-only token is appropriate for acceptance testing, but is a server permission choice rather than v2's permanent capability boundary.

## Architecture

Home Assistant ingress UI → standalone v2 API → Ollama-compatible model/function-call loop → Streamable HTTP MCP client → connected Hubitat MCP server.

The live server catalog is refreshed and paginated per request. Gateways accept empty calls for schema discovery and `tool`/`args` calls for execution; flat catalogs are supported. No fixed tool names or gateway-membership maps are enforced by HomeBrain. Unadvertised top-level tool names are refused; the server resolves gateway leaves and applies its own access checks. Tool calls are sequential and not automatically retried after an uncertain outcome.

The bundled upstream `SKILL.md`, `safety-guide.md` and `rule-patterns.md` are unmodified, pinned to upstream `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0` and include the MIT license. All three are supplied to the model. Live schemas and `hub_get_tool_guide` are authoritative. New automations should prefer native Rule Machine/Visual Rules; the bundled rule patterns describe legacy custom rules.

Calls carrying `confirm=true` pause for an explicit UI decision tied to one pending call and request. Approval is not inferred from assistant output or tool content, does not persist for another action and does not bypass hub backup or permission checks. Ordinary requested operations follow upstream identity and access guidance. No real device, rule, hub setting or permission is changed during repository development.

Credential redaction, per-call operational timeouts, the request deadline and explicit context truncation remain. These are resource/privacy safeguards, not answer-quality patches. The model owns the investigation and final prose.

## Evidence and recorder

Receipts contain the bounded, redacted source response shown to the model, with arguments, status and timing. Completed receipts survive later model failures. Receipts are browser-session responses, not durable archives or automatic follow-up context.

The external recorder source is unchanged from v1 and writes v2's independent SQLite file. No automatic v1 migration. Its UI/API read that database; the model's MCP loop does not automatically ingest recorder history.

## Verification history

- PR #1524 introduced the isolated alpha.1, merged as `fd02765b2e4ffa328445e3b41abb9ce147e87749`. The full check-runs endpoint verifies nine successful checks on development head `2f390e65efa4fb1312c903118bafde9545101769`. The v2 PR test log checked out synthetic merge `8215d43bc3635c08a00c381b02b5eddf50c1851e` and ran 10 tests.
- PR #1525 introduced alpha.2 receipts and a frozen read allowlist, merged as `9e2f345c076aed9f3c271faa1794457b8ca7ab8e`. Eight checks passed on its final head; 11 v2 tests. The allowlist diverged from the now-clarified upstream scope and is removed in alpha.3; receipt improvements remain.
- Alpha.3 CI/merge evidence is recorded on [PR #1526](https://github.com/ienam-smarthome/HomeBrainOS/pull/1526). Review the final head and actual workflow checkout before claiming validation. CI includes protocol/confirmation regressions, JavaScript syntax and amd64 Docker import/HTTP startup. It uses no live hub/model credentials.

## Installed alpha.3 interface mismatch

User-supplied logs confirm installed amd64 alpha.3 started and served status, but Ask returned HTTP 403 before model/MCP execution. The screenshot retained alpha.2's "read-only pilot" UI, and the log shows no new GET / after the alpha.3 restart. This supports an older open/cached page submitting without alpha.3's required request header; no live reasoning result was obtained.

Alpha.4 adds no-store response headers, bypasses cache on API fetches, displays the interface/backend version and checks that they match before Ask. A mismatch offers a cache-busting reload preserving the ingress path. Missing-header refusals explain how to reload. The request-header/confirmation safeguards remain enforced; no model or MCP behavior change. Close/reopen and refresh any already-open old page once after updating. Fix CI/merge evidence is recorded on [PR #1527](https://github.com/ienam-smarthome/HomeBrainOS/pull/1527); live recovery remains pending.

## Alpha.5 live tool-contract and schema-preservation fix

The supplied installed trace made seven calls with a gateway selector nested inside `args`. Every result was a schema catalog; no inventory/history query executed. The model's claim that devices could not be found was unsupported. Regex redaction also corrupted the embedded catalog JSON at `include_token`. This is failed live first-answer acceptance, not an empty hub or successful investigation.

[PR #1528](https://github.com/ienam-smarthome/HomeBrainOS/pull/1528) first adds synthetic tests on pre-fix commit `62b54ac1fcff2dc62168d3fdbad241327a523579`. CI reproduces all seven malformed shapes reaching the server, scripted discovery failure, JSONDecodeError and erased schema property definitions. No private household source is committed.

Alpha.5 validates arguments against raw live schemas using an offline reference registry. Gateway shape comes from schema properties, with no tool-name inventory. Payloads that omit a top-level selector while supplying nonempty nested arguments are rejected locally with the correct upstream call convention; the model can repair its next call. No silent argument rewriting or automatic tool retries. Empty discovery, tool-only invocation and valid flat/gateway calls are retained.

JSON-bearing text is parsed before credential redaction. Schema names/types/required fields/enums and JSON structure are preserved; actual credential values and defaults/examples are removed. Unchanged JSON source retains original formatting. Schema discovery is explicitly labeled as such in model context and receipts, with `operation_executed=false`; the original source is retained. No answer rewriting, fixed investigation sequence, upstream skill edit, heating-specific logic, v1 change, recorder change or permission bypass.

Final correction CI/merge evidence is tracked on PR #1528. Scripted recovery through discovery, inventory and history verifies the lifecycle, not Gemma reasoning. Real-model first-answer uplift and matched Thaura/Claude comparison remain unmeasured. Next: install alpha.5 and preserve fresh first-answer receipts without coaching or retries.

## Next acceptance

1. Install/update v2 alongside v1; verify ingress and real model/MCP connectivity. Other advertised architectures require deployment acceptance beyond the amd64 smoke.
2. Use an upstream read-only client token for first-answer investigation comparisons. Ask the same frozen question with no prompt repair and preserve answers/receipts.
3. Compare lighting, humidity, heating and hub-incident questions against matched v1/Claude/Thaura evidence. Publish sample counts, provider/model, code version, latency, missing sources and unsupported claims; do not claim quality from unit tests.
4. Test device control and native automation only with explicit user-authorized test operations and upstream safety requirements.

Live first-answer usefulness, factual grounding, model comparison, control/automation behavior and Home Assistant installation remain **not measured/unverified**. No unattended development is implied.

## Alpha.6 UI conveniences and current evaluation direction

User requested separate answer/technical-detail copying and visible response time. Alpha.6 retains the original API response in copied technical details, alongside question, model, request ID, browser elapsed time and server elapsed time where available. LAN HTTP clipboard fallback and failed-request copying are covered by isolated UI tests. Model, prompts, schemas, MCP access, recorder and answer generation are unchanged. No live model or hub calls are used for this UI validation.

Current evaluation direction: assess existing Ollama Cloud Gemma4:31b with varied read-only first-answer questions; preserve all failures and raw receipts before deciding any changes. Do not resume model routing experiments, heating-specific fixes, coaching or answer rewriting. This UI release makes evidence easier to capture; it is not evidence of reasoning improvement.

## Alpha.7 daily-use interface and evaluation direction

User authorized v2 usability development and continued comparison with v1 before choosing a daily assistant. Alpha.7 adds safe DOM-only Markdown/table/code rendering, original-text access, page-session conversation history and reset, evidence JSON download, responsive spacing/focus styles and a visible recorder-disabled explanation. It also corrects the diagnostics tab ID mismatch. Copy operations preserve original answer text; no raw HTML is interpreted. No transcripts are persisted by this UI.

Model prompts, upstream skills, agent/MCP code, permissions, recorder source and v1 remain unchanged. Follow-up context remains prior prose only, not prior tool receipts; the UI explains this. Formatting is not answer rewriting or proof of factual accuracy. Confirmation controls remain attached to backend operations.

Local UI regressions cover formatting/XSS, raw copies, downloads, session reset/history, busy-state reset refusal, timing/errors, diagnostics empty state and tab target. CI includes Python runtime and Docker startup. Installed desktop/mobile acceptance and day-to-day usefulness remain pending.

Recent evaluation: Gemma can summarize richer frozen G06 evidence but previously looped on tool selection; Beam also made unsupported claims. Production-code replay is byte-verified. Fresh investigation comparisons remain limited by captured-query coverage; the latest expanded attempt timed out before either first model response. Do not infer a model winner, train case-specific skill rules, or replace the default model based on those runs. Private fixtures/tokens remain outside the repository.

## Alpha.8 — evidence-aware session follow-ups (8 November 2026)

The user approved the next evaluation milestone and correction of the alpha.7 follow-up limitation, while asking to retain existing upstream MCP write permissions and confirmation behavior unless a serious risk is shown. The alpha.7 UI sent only prior prose; source receipts did not survive into model input on subsequent questions. Alpha.8 introduces a small server-origin, redacted, **memory-only** receipt cache keyed to the open browser conversation. Prior source excerpts include tool identifiers, arguments, capture time, success, bounded result text and truncation markers. The client does not submit source receipts; only the agent's actual tool responses are retained. Old values are historical and cannot authorise new device writes or substitute for a necessary fresh check. The model remains responsible for interpreting them and selecting further tools. New conversation rotates the ID and erases server-held evidence, and expiry/eviction bound memory.

The upstream skill files remain unchanged. V1, recorder source, provider routing, server permissions, `confirm=true` approval, and tool selection are unchanged. No deterministic causal fixes, automatic retries or per-incident logic were added. A server-side cache gives stronger receipt provenance than trusting arbitrary browser-provided observations; the UUID remains a session capability, so preserve normal Home Assistant ingress and keep the direct port disabled.

**Evidence gate:** Browser/HTTP/Python regression tests verify the data flow, truncation, masking, reset, expiry and isolation using synthetic MCP/model responses. The private G06 first-answer capture and Ollama Cloud credentials are not part of the repository. No live Hubitat/Gemma replay or matched Claude/Thaura evaluation is asserted. The next installed acceptance uses the frozen cross-domain matrix in `docs/HUBITAT-MCP-AI-V2-ACCEPTANCE.md` and exported first-answer technical JSON, including at least one dependent follow-up per domain. Previous timeouts are failures, not a successful comparison.

CI and PR exact-head verification: **pending until the final candidate passes.** No unattended work runs after this session.

## Alpha.9 — real follow-up source loss and generic readback milestone (8 Nov 2026)

The user provided three installed alpha.8 technical JSON exports from a read-only cross-device heating question and two follow-ups. The first answer had **10 tool attempts, 2 local contract rejections, 8 successful reads**, including the main controller's 58 returned events and five radiator histories. The first answer incorrectly reported a most-recent interval and extrapolated later snapshot values backwards. Each follow-up was fast but used **five prior snippets and zero new MCP tools**, falsely asserting that original main controller history did not exist. The complete original receipt was present in the first technical export but absent from the alpha.8 follow-up excerpt budget. Individual device event histories were bounded (some showed 100 recent events), so absent older events in those pages were **not** evidence of historical absence. Do not commit private device history or real model outputs to the public repo.

Root cause addressed: alpha.8 kept short latest-first source excerpts without an index of *all* prior reads. Alpha.9 adds compact provenance and returned event-time span metadata for every retained source plus a server-side capped archive of each redacted original source string. A single read-only client-owned model tool retrieves older source chunks on demand by opaque receipt ID. The model can also rerun a correctly scoped native MCP read if the old archive is incomplete. It is **not** an automatic replay mechanism, local causal verifier or expanded write capability. This general mechanism applies to lighting, humidity, heating and hub-incident histories alike.

Operational protections: one session UUID, source IDs scoped within it, memory-only, bounded index and bytes, explicit truncation/eviction signals, no new Hubitat writes, existing upstream confirmation/permission boundaries unchanged. Preserve `New conversation` reset and 45-minute idle expiry.

**Acceptance:** scripted test sources must reproduce an earlier important record followed by several large newer sources, verify the earlier source appears in the index even when excerpt truncated, prove the model can request the original in chunks without contacting Hubitat, and fail closed for wrong/expired IDs. Live alpha.9 result still requires a first uncoached answer and dependent follow-up; do not claim corrected Gemma reasoning merely from tests.

PR, exact-head CI, final status and merged SHA: **pending verification**.

## Alpha.10 — cause vs hypothesis evidence standards (8 Nov 2026)

A real alpha.9 heating-history follow-up correctly found only 11 filtered events per TRV, then asserted a Hubitat event-retention ceiling was the **most likely** explanation and claimed no further MCP query could recover the records. The answer ran in one model round, with 13 prior indexed sources, 11 snippets and **zero** new read calls or local prior-evidence retrievals. It did not compare native Event page records, inspect alternative return-source coverage, or independently verify purging. **Cause remains unverified.** This error generalizes beyond heating: a limited observational result does not distinguish retention, limited endpoint result, reporting gaps or query behavior.

Independent review of the upstream MCP v5.1.7 Groovy implementation shows `_fetchBypassDeviceEvents` uses `hubInternalGet("/device/eventsJson/${deviceId}")` and `_deviceHistoryBypass` applies attribute/date/limit filters to that returned array. This does not establish the endpoint's depth or native store retention. References: `kingpanther13/Hubitat-local-MCP-server` `libraries/mcp-devices-lib.groovy` around lines 692–710 and 3151–3194. **Do not claim native-hub purge without independent comparison.**

Implement a **general** client-side `client_event_source_scope` annotation, preserving the original model-visible MCP `content`, with returned count, returned event timestamps, requested time/limit scope and explicit unknown completeness/causality. Add short model-led evidence discrimination guidance to the v2 prompt, not incident-specific instructions, vetoes, mandatory extra rounds, answer rewriting or a new causal planner. The evidence annotations are derived from the same returned rows; they do not independently certify a cause. Real alpha.10 first-answer reasoning and native Hubitat Events-page cross-check remain unverified.

Scope: `hubitat-mcp-ai-v2` and v2 development notes only. Existing user-approved upstream write/confirmation behavior remains untouched. The native Hubitat Events-page comparison needs authorised local inspection; repository development alone cannot see the hub. The private exported technical JSON does not belong in Git history.

PR merge SHA/CI: pending exact-head all-green check before merging.

## Alpha.11 — unambiguous model-facing live gateway schema (8 November 2026)

The installed alpha.10 Gemma4 cloud reboot investigation supplied by the user returned a well-supported firmware-update/startup sequence but required **six** model rounds and **five** MCP attempts, of which only **two** succeeded. Three attempts used malformed gateway arguments (selector nested under `args`, then repeated as leaf `args.tool`, including a similar diagnostic gateway error). These were model-generated protocol mistakes, not hub failures. Exact private technical JSON remains outside GitHub.

Enhance the **presentation** of any server-advertised gateway-shaped `inputSchema` (detected by *both* `properties.tool` and `properties.args`, no name lists or hard-coded leaf schemas). Use a deep copy for model-visible descriptions and top-level `additionalProperties: false` matching existing server gateway enforcement; retain the live enum, leaf selection authority, normal/flat tools, catalog discovery `{}`, original validation schema and upstream skill verbatim. The model continues selecting the gateway and leaf. A non-gateway tool with an `args` object containing an ordinary `tool` data key must not be affected.

Additionally reject the duplicated leaf selector `args.tool` locally for gateway-shaped schemas before any `tools/call` request; never guess, reparent, autocorrect or retry. Preserve existing permission and approval contract: writes are still upstream-authorized and confirmed only per current rules; no write is executed by this release itself.

Synthetic regression tests cover live enum retention, model-facing call shape, original catalog immutability, unrelated direct tools, no-network duplicated-selector rejection, unchanged good-call payloads, discovery and a scripted first model call. The scripted model is **not** a real Gemma evaluation. Native source scope sidecars, alpha.9 prior-evidence archive, external Hub Diagnostics recorder and v1 remain untouched.

Post-merge installed alpha.11 quality acceptance **pending**: exact version, uncoached read-only first attempts in unrelated domains, complete technical JSON, malformed-call rate, model rounds and answer support. Avoid promising error-free Gemma behavior until observed. PR/merged SHA and CI to verify.

## Alpha.12 — discover selected leaf contracts from upstream (8 Nov 2026)

The latest installed alpha.11 first-answer reboot analysis answered the firmware-update question with defensible source records and no selector-placement errors, but incorrectly used `hub_get_logs(mode=hubEvents,sortBy=desc)` and spent 5.24 seconds on an unrelated `past` log dump. The upstream v5.1.7 `hub_get_logs` **leaf** inputSchema, found in `libraries/mcp-diagnostics-lib.groovy`, describes `sortBy` as applicable to `devices` and `apps` modes. The top-level `tools/list` gateway schema cannot express every leaf's field-specific restriction. No hardcoded remedy for `hub_get_logs` or individual modes is appropriate.

Model-selected, generic implementation: after a selected gateway leaf is proposed, fetch that gateway's `{}` metadata-only catalog once per unchanged connected catalog, cache the available `inputSchema` and descriptions, and check only structurally declared JSON Schema constraints. Return local, nonexecuted `contract_error` for invalid typed arguments. Include the selected leaf schema/description in the model's **next** tool definition and later requests. The client does not extract hardcoded natural-language restrictions into invented validation rules. A prose-only restriction can still yield an upstream error on first use; this limitation must be visible, not masked. No hidden mutation, automatic retry, source-query replay, new authorizations or fixed model rounds.

Operational scope: read-only schema fetches are additional MCP metadata requests, tracked in `leaf_schema_discoveries`, not device reads. Cached selections invalidated if live tools/list changes. Optional metadata failure must not prevent a previously valid native tool call or gate writes differently. All user-owned device/tool permissions, `confirm=true` approval, upstream skills, v1 and external recorder unchanged. Model remains responsible for search and stop decisions.

CI uses a synthetic MCP server exposing multiple leaf schemas and a stub model; tests verify one catalog probe per gateway, cache invalidation, field descriptions, local validation without a native side-effect, exact passthrough of valid requests and unchanged direct tools. Live installed Gemma performance **unverified**; compare real first-attempt technical JSON before recommending further changes.

PR head, exact CI results and merge SHA: pending verification.

## Native flat MCP vs gateway evaluation — no v2 runtime change (8 Nov 2026)

The user requested comparison before any further architecture change after alpha.12's live Gemma result: three malformed nested gateway selector attempts, one invalid `sortBy='desc'` leaf request (locally rejected), and four eventual successful reads in 13.78 s. Alpha.11 first-call gateway formatting had been better, so the observed difference may reflect model variability; one run cannot establish an alpha.12 regression rate. The separate claim about free-memory history must still be checked for appropriate incident-time coverage.

**Upstream code finding:** the native Hubitat MCP server already offers a genuine flat catalog via its existing `useGateways=false` (**Consolidate tools behind category gateways: OFF**) setting. In this mode the server advertises every visible leaf with its direct inputSchema on `tools/list`; it enforces the same Read/Write masters and advanced overrides, hides `hub_search_tools`, and explicitly refuses stale gateway-name calls. The setting is **server-wide**, affects other clients' catalog assumptions, and must be restored after an authorised test. V2 already accepts direct leaf calls and validates the live top-level schema. There is **no evidence justifying a new client-side proxy** or a version bump just to try native flat mode.

Added synthetic gateway-versus-flat compatibility regressions with identical mocked event results and test isolation of hidden writes, confirmation and catalog refresh. Real installed Gemma context size, model success, tool latency and hub-side flat-mode behavior are **unverified**. Only a controlled read-only A/B on the installed hub can decide; see `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md`. Do not change Hubitat settings, credentials or permissions from this repository work. The user must knowingly accept the global mode switch before it occurs.

Repository evaluation test PR/CI: pending.

## Three installed flat-mode runs — provisional choice (8 Nov 2026)

The user switched upstream MCP Server `Consolidate tools behind category gateways` OFF and supplied three complete first-answer Gemma4 cloud Technical JSON exports from unchanged v2 alpha.12. **Results:** G1 reboot 5.792s, 1/1 tool success, 2 rounds; G2 five recent device events 8.815s, 2/2 successes, 3 rounds; G3 OFF-cause investigation 11.962s, 5/6 successes, 7 rounds. Combined: **8/9 native tool attempts succeeded**, **one local type-schema rejection, zero nested gateway-selector failures**, and average **8.856s** wall time. All three answered the primary request; G3 independently retrieved the automation and two motion sensors. The configured 15-second inactive delay and the last motion-inactive event preceding the OFF command by 15.128s strongly support the proposed mechanism, but do not establish an independently logged timer callback or exclude all alternatives.

The matching alpha.12 gateway **G1** took 13.779s and 4 rounds, with 4/8 model attempts successful and one leaf catalog discovery. Flat mode G1 used 5.792s, 2 rounds, 1/1 success, no discovery. This is one measured paired improvement, not a reproducible performance distribution. G2 `prior_receipts_used=1` is not a perfect isolated first-turn comparison. No other mode-matched causal trial exists yet. Source-output confidence is still overcalibrated: the model sometimes asserts a cause is completely verified when temporal correlation/configuration only strongly supports it.

**Important safety uncertainty:** `do not change anything` and observed read-only operations do not verify *effective* token permissions; a separate earlier `hub_get_info` response reported `writeEnabled:true` but not all per-client grants. Verify Read allowed / Write denied on the actual test client without using a write as a probe. The server-wide flat-mode switch also affects other clients and may need rollback. No device settings, token permissions or MCP server settings were changed through this GitHub development update.

**Development decision:** Preserve the working alpha.12 runtime and model-selected direct tools, no v1-style causal planner, no new router or hardcoded input corrections. Native flat mode is the leading observed candidate only, not a universal default. Freeze F1 humidity and F2 multi-room heating first-answer questions for a broader evidence-timing and cross-domain test; see `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md`. Only aggregate results may be committed. Live client access and other connected-client compatibility are not verified by GitHub.

## Alpha.13 — browser rendering and flat-mode heating-answer review (8 Nov 2026)

The user supplied a screenshot of a raw TeX escape rendering in an alpha.12 historical room-heating comparison, together with the complete first-answer Technical JSON from the installed flat-mode Gemma4 cloud model. The table showed literal `$21.0^\\circ\\text{C}$`, `$\\rightarrow$` and `$\\sim$`. The frontend's `renderAnswer`/`appendInline` implements a deliberately small Markdown subset with no math handling, so the defect was strictly **display**, not a bad MCP result or historical event corruption.

**Implementation:** Add a narrowly bounded, offline inline-TeX-to-safe-text display layer for common symbols (`°C`, arrows, inequalities, approximations, Greek symbols, numeric exponents/indices). Preserve Markdown code literals, original API answer text, raw-view/copy/export, all event receipts, and any unsupported TeX unchanged. No HTML parsing or external library/CDN, no math evaluation, no model-specific output instructions or cause-specific fixes. Tests cover UI VM and Chromium desktop/mobile as well as XSS and exact technical JSON preservation. Bump UI/service/add-on to **alpha.13** so ingress refreshes correctly. Complex formulas (e.g. fractions and matrices) are intentionally **not** typeset by this small renderer.

**Source-verified answer assessment:** Eight direct read-only MCP calls, **8 successful, 0 rejected**, 4 model rounds, 15.893s browser / 15.831s server, no prior receipts or schema discoveries. The main thermostat reported `heating` at 09:33:33 UTC, `idle` at 10:00:22; one bedroom TRV reported `heating` from 09:30:15 to `idle` at 10:00:03 and had actual device-reported heating-setpoint changes from 22 to 21 degrees. Four other TRVs returned no thermostat operating-state rows in their **requested 09:30–10:10 UTC** history excerpts, though some unrelated rows or setpoint **commands** were present. Thus the conclusion “not all TRVs were idle” is supported, while the other four states remain **unverified**, not demonstrably idle. Model table called commanded setpoints “Observed Setpoint Change” for these devices, which overstated evidence. It also said no main-thermostat setpoint change was recorded without querying that setpoint attribute. Correct future investigations should distinguish command receipt, confirmed physical state, and absences limited by returned source coverage; this is documented, **not** enforced with any new planner/claim patch.

Native flat mode remains the *observed leading interface* but not a proven universal default. A previous report of enabled write permission still requires client-specific verification before treating a natural-language read-only question as an enforced permission. No live Hubitat, HA, router or upstream server modifications in this repo release.

PR head, CI and merged SHA: pending final verification.

## Alpha.14 — native load line repair and source-scope guidance (8 Nov 2026)

The user's installed alpha.13 screenshot of **Hub Diagnostics → History → 24 hours → Native 5m load** showed many isolated dots during the hours with recorder samples. Code review found a definite local mismatch: the recorder's raw (short-history) `samples` array contained repeated 30-second polls holding one cached native five-minute observation, while only the first source-labeled row had a `diag_segment`. The canvas renderer tested successive rows for equal `diag_segment`, causing repeated cached rows to be rendered as tiny strokes. The graph is **not evidence that the hub had dozens of independent native measurements or outages**. No external recorder SQLite or real probe responses were available to independently verify specific timestamp/collection anomalies. Empty earlier portions of a 24-hour range can be explained by a recorder that began collecting later or by unavailable readings; do not invent historical data.

**Repair:** For native-only values, only return one source-labeled row per distinct native source label in raw chart history (long-window logic already deduplicated). Preserve raw poll count separately, all original OS-memory probes and failure segment detection, 15-minute true native gap boundaries, exact source/collector timestamps, and actual extrema. Add visible native-line connections and small markers, fractional Y tick precision, a caption showing observation/poll counts, and browser regression on desktop/mobile confirming two connected genuine segments but not across the true 20-minute gap. **The separate CPU-equivalent percent is derived from five-minute load / configured cores**, not a direct hardware utilisation metric.

Generic model-led answer quality: extend only the source-integrity skill guidance, requiring the model to compare any all/none/every group conclusion against actually checked members, attributes and time periods, to distinguish commands from confirmed device-state changes, and to qualify missing/empty bounded reads as unverified. No automated veto, rule-specific patch, fixed planner, artificial model rounds, device changes, permission updates or model routing are introduced.

Version `2.0.0-alpha.14` for backend, add-on and UI. Tests: native short history dedupe, native longer-history extrema, true outage/long-gap segmentation, unchanged externally sampled OS series, canvas line continuity and tick decimal labels in Chromium and existing UI/model safety tests. First real installed UI verification pending. PR head, checks and merge SHA pending.

## Alpha.15 — V1-quality independent timeline UX (8 Nov 2026)

User feedback after confirming alpha.14 native sampling graph repair: **V1 still has significantly more useful and functional graphs.** Their V1 screenshot illustrates source-aligned memory and CPU panels on separate scales, point cursor/time readout, a local incident/event summary, accessible detailed chart with statistics, and investigation buttons. V2's prior combined/detailed canvas was valid source data but less usable, especially over a 24-hour range when recorder history covered only six hours. Do not mistake the UI shortfall for a native Hubitat CPU telemetry defect.

Implement an **SVG unified timeline in v2**, using the existing external SQLite `/api/diagnostics/timeline` response. Default aligned split memory (external probes) and CPU load equivalent (native five-minute measurements), optional shared plot with independent axes. Include nice source-specific grid ticks, genuine source continuity and exact timestamp cursor, native label and source provenance, offsets/confirmed system starts, external outage bands and observed extrema in a bounded event list. Buttons inspect **only stored source records**; prepare an AI question in the Ask tab without executing tools or authorising a write. Open original same-origin JSON via normal link. No V1-only historical journal UI or automatic model invocation.

Also improve the existing V2 detailed metric graph with unit-labeled axes, min/max/latest stats, keyboard/touch point inspection, and the same time window controls. Choose 6h initial range and default to **fit data** to avoid showing a mostly blank 24h axis when only recent observations exist. Explicitly allow **full requested range** to show blank periods; no missing data is backfilled, nor is fit-mode a claim of earlier complete coverage. Preserve real data extrema, recorded gaps, causal qualifiers and recorder independence, and keep V1 entirely untouched.

Synthetic browser and JS regressions test UI behavior in both desktop/mobile widths, with no live Hubitat or model calls. Existing alpha.14 recorder dedup, MCP native flat mode, permissions, source-scope inference policy and complex-math display unchanged. Installed review pending.

## Alpha.16 — raw native load vs core-normalised percentage (8 Nov 2026)

The installed alpha.15 phone screenshot shows **Native 5m load** axis and tooltip expressed in load-average units (native value approximately 0.6). Although the V2 **Unified incident timeline** already charts native load-equivalent **%**, the *Detailed metric history* dropdown selected the unscaled `native_load5` field and therefore showed `0.6 load`. User requested that native load be presented as a percentage.

Source audit confirms `external_hub_diagnostics._with_load_pct()` already derives `native_load_pct = round(native_load5 / cpu_cores * 100, 1)`; it exposes `cpu_cores` in the history and status responses, and `native_load_pct` is a permitted history metric. No new recorder calculation, inferred core count, data persistence changes or Hubitat read needed. **The derived value is five-minute load-equivalent percent, not direct CPU utilisation**, and values over 100% remain legitimate demand indicators; do not clamp to 100%. The raw native load is preserved separately for expert inspection.

Only the detailed chart metric selector/legend/provenance/cursor and v2 version require changes. The main option now selects live `native_load_pct`, the raw `native_load5` remains a secondary option, and the caption reports configured source core count and normalization. The combined timeline and original historical readings are unchanged. Browser tests must inspect actual `%` labels and native source gap behavior at desktop/mobile sizes, plus raw-load reversibility and exact source-time alignment. Python regression verifies source raw values remain immutable and backend normalisation uses configured core count. No V1, MCP permission, model, hub or SQLite mutation.

PR/CI and installed acceptance: pending final check and first user screenshot.

## Return to original v2 agent-quality roadmap — first-answer measurement

The next milestone is **not another Hub Diagnostics feature**. The original v2 problem after native flat-tool improvements is **correct, source-complete model-led investigation on first attempt**. Repeated multi-TRV and motion-timer answers show source selection and output-claim confidence still need evidence-grounded evaluation. Five-minute load display is complete and separately verified via alpha.16.

New **purely offline** script in hubitat-mcp-ai-v2/tools/first_answer_audit.py accepts the browser's private Technical JSON. It outputs bounded *counts and evidence-observation limitations* without disclosing private answer text, request parameters, device identifiers or event records. It reports native calls versus metadata reads, rejected operations, prior evidence, source-reported event rows, sample-dependent latency, and **not_measured** quality fields. The importer does not access the model or hub and never grades truth from lexical text or successful MCP calls.

A new freeze-and-review protocol covers reboot, lighting cause, humidity duration, historical room-demand, FanBoost and offline/stale-telemetry cases; see docs/HUBITAT-MCP-AI-V2-FIRST-ANSWER-QUALITY.md. The earlier curated 40 source-only packets remain separate from live native MCP benchmarks; passing one is not evidence of the other.

**Next user action:** one fresh V2-R5 FanBoost read-only question, first answer + Technical JSON, with effective test client's Read allowed / Write denied verified through configuration (no write probe). Then assess source coverage and provenance before planning model-quality code. Do not interpret this tool/CI milestone as validated Gemma quality or a new alpha.17 runtime. PR #1542 merged as `4e486befbc2c`; the merge commit's Release assurance, v2 pilot, Answer quality scorecard integrity and Validate HomeBrain OS workflows completed successfully.

### 8 November V2-R5 first-answer review (no runtime change)

The user provided an actual private alpha.16 Gemma cloud Technical JSON for the frozen FanBoost question. A direct source review found 13/13 successful native calls across six model rounds, 18.480 seconds browser elapsed, and three event-history responses with 19 combined rows. A scheduled-cycle interpretation was **strongly supported**, but Gemma falsely declared the cause fully verified and claimed all configured humidity sensors were below threshold despite missing focal-time humidity coverage and not querying one configured sensor at all. App command issuance and physical reporter were recorded; the precise internal scheduler callback was not. Assessment: **PARTIAL** first answer, **causal certainty overclaim**, **incomplete monitored-sensor historical coverage**. No cross-domain quality denominator is yet available; no production reasoning code patch justified from one case.

The approved evaluation-only audit tooling must now recognise actual native `content[].text` event-row responses even when no `client_event_source_scope` annotation exists. This is separate from the previous successful-only scope filter and must not infer event uniqueness, upstream retention, complete windows, or cause. Preserve the private raw export outside GitHub. The next recommended frozen question is V2-R3 (historical humidity thresholds). No Hubitat/HA/recorder/MCP setting or runtime version changes.

### V2-R3 historical evidence baseline and alpha.17 candidate (8 November 2026)

The frozen V2-R3 question on installed alpha.16 yielded two successful direct MCP reads, three model rounds, 9.808 seconds browser latency, and 11 returned event-history rows. The observed threshold-interval arithmetic was correct, but the answer falsely claimed the sampled history proved uninterrupted conditions. `isStateChange:true` and a successful 24-hour query do not independently certify continuous history. The first answer is reviewed as **PARTIAL**; raw readings and timestamps remain private, outside the public repository.

Together with the independent V2-R5 first-answer review, there are now two cross-domain **partial** source-reviewed results despite 15/15 successful native read calls. The sample size is too small to assert a model-wide rate.

**Alpha.17 candidate:** extend the generic model-visible native event-scope metadata with UTC-normalised adjacent-returned-timestamp spacing and an explicit `can_infer_uninterrupted_state_between_events:false` limit. No fixed planner, claim patch, rewrite, extra model call, permission change, recorder update or V1 change. The next acceptance is a controlled alpha.17 first-answer comparison against the frozen V2-R3 question, followed by another independent domain. Effect on model quality remains unmeasured.

### Evaluation-only audit integrity follow-up (candidate)

The offline Technical JSON importer must not inflate event-history coverage from a failed MCP call or a metadata-only schema/catalog receipt that happens to contain a scope-shaped JSON object. Limit counted event histories to successful native source responses, explicitly count discarded scope-shaped receipts, and preserve **unknown unique event count** across overlapping responses. Also avoid echoing externally supplied model/tool names or argument keys in supposedly private-safe aggregate exports; use a model fingerprint and structural counts instead. This is an evaluation-format v2 update **without runtime or add-on version change**. The live answer-quality baseline remains unmeasured pending the frozen FanBoost first answer.

### Installed alpha.17 first-answer comparison — V2-R3 (8 November 2026)

The user supplied the **first answer and private Technical JSON** from the installed alpha.17 UI. It answered the exact same frozen humidity-history question with the same Gemma cloud model and native flat MCP tooling as the prior alpha.16 baseline. Both were first turns with no prior evidence receipts. Source comparison: 11 returned humidity rows in each run, **10 identical event timestamp/value pairs**, with one oldest/newest row changing as live history advanced. Both selected two native reads successfully and completed in three model rounds. Browser latency was **9.808s (alpha.16) vs 7.886s (alpha.17)**; server latency **9.740s vs 7.841s**. This is one observation, not a repeatability or performance distribution.

**Supported improvement:** alpha.16 incorrectly claimed continuous recorded history and uninterrupted conditions between two reported threshold observations. The alpha.17 answer explicitly described discrete reports and gaps, and **did not repeat the unsupported continuity claim**. The new source-scope gap metadata was present in the actual model-visible event response, including 10 adjacent timestamp pairs and `can_infer_uninterrupted_state_between_events:false`.

**Remaining limitations:** The model still described *first observed* threshold readings as actual physical crossing instants, used an unquantified “slightly before” statement, labelled a returned maximum as a peak without complete intermediate coverage, and referred to a same “session” without independent session evidence. Reviewer outcome: **improved PARTIAL**, not a full pass, model-wide accuracy score or causal claim that the extra annotation alone produced the change. Effective per-client Write-denied permission remains unverified by observing read-only calls.

**Development decision:** Keep alpha.17 unchanged. Do **not** respond with another instance-specific instruction, planner, model routing experiment or answer rewriting. The next discriminating test is the frozen V2-R2 light OFF investigation in a new conversation under a verified read-only client, with first answer and full private Technical JSON. Transfer to the separate causal-reasoning domain remains unmeasured. No Hubitat, HA, router, MCP server, model setting, V1, recorder, or permissions were mutated during this repository review.

### Installed alpha.17 V2-R2 lighting first-answer review (8 November 2026)

Reviewed the user's **unedited first answer and private Technical JSON** for the frozen Hallway Light 1 OFF investigation. Same alpha.17/Gemma native-flat environment, zero prior receipts. Runtime **15.004s browser / 14.917s server**, seven model rounds, six MCP attempts: **five successful reads, one client-rejected live-schema type error** (`appId` number instead of required string, corrected on retry). Three event-history calls returned 24 rows overall; the 20-row focal-light query reached its requested limit, so returned evidence was not an exhaustive older history.

**Grounded:** exact command issuer recorded as the controller app, distinct subsequent bridge-produced OFF state, two configured motion sensors with recent inactive events, enabled inactive-off configuration, and a time interval matching the configured inactivity delay. The motion event `triggered[]` records prove the app handler was a listener, **not** that a particular internal timeout callback executed. No app-execution decision trace was retrieved. Current app config was not a timestamped historical config snapshot.

**Reviewer result: PARTIAL** — excellent supporting correlation, but the model asserted the internal timeout mechanism and upstream cause were **verified**, when they were only **strongly supported**. Its wording also called the bridge-reported state a physical confirmation. This is not a tool-data identity failure. The avoidable schema-type rejection is an efficiency defect, not evidence of a device write or protocol outage. No write calls appeared; effective Write-denied permissions remain unverified by the transcript.

**Cross-domain direction:** The matched V2-R3 alpha.17 result showed improved description of discrete history; V2-R2 still overstates inferred app-internal causality. Avoid another incident-specific patch, forced tool workflow or answer rewriting. Keep alpha.17 and the native MCP model-led design, then run frozen **V2-R4 heating** on a fresh read-only test conversation to assess complete historic multi-device coverage, actual setpoint/operating state, and causal certainty. Only after independent source-review evidence should a new general-purpose runtime change or model comparison be proposed. Private raw logs and device event records remain outside GitHub.

### V2-R4 historical heating first-answer / alpha.18 UI update (8 November 2026)

The uncoached alpha.17 heating first answer was independently source-reviewed against the complete private Technical JSON. **17.575s client / 17.497s server, four model rounds, 10/10 successful native reads, zero prior receipts**. The model found the main thermostat and six named TRV devices, queried the main historical operating-state/setpoint/temperature and five room TRV operating-state histories (one empty), and correctly identified overlapping heating reports and subsequent idle states. It **did not query any TRV historical heating setpoints/temperatures**, and the additional listed TRV had no comparable operating-state attribute in the inventory; that group scope was not explicitly resolved. It nevertheless inferred physically closed valves, active boiler firing and an upstream causal relationship from timestamp coincidences and discrete operating-state events, none of which were independently recorded. Reviewer: **PARTIAL**, useful but insufficient group/attribute and physical-source coverage. A successful native tool receipt does not establish historical source completeness or physical truth.

New user-requested interface work is **alpha.18, UI-only**: on copying answer or technical details, show a prominent green **“✓ Copied!”** label on the action button plus accessible status beside Answer; on failure show a visible **Copy failed** state. Feedback clears after a short delay and is invalidated on new requests/conversations. Preserve the raw copied text and Technical JSON, LAN clipboard fallback and independent diagnostic recorder. No new model prompt, tool routing, MCP call, permission change, V1/HA/Hubitat device write or evidence correction layer.

**Decision:** Keep native model-led reasoning; do not add heating-specific fixes. Next frozen read-only first-answer evaluation is V2-R6 offline/stale telemetry using the same cloud model and live native flat tool contract with verified Read allowed / Write denied test-client configuration. The UI release needs CI and installed copy acceptance; model-quality effect from UI change is **not measured / none intended**. Source payloads and household event times stay private.

### V2-R6 stale-device first answer and bounded-log audit follow-up (8 November 2026)

The user supplied the original first answer and private Technical JSON from UI alpha.18, `gemma4:31b-cloud`. Browser elapsed **16.554s**, server **16.483s**, **four model rounds, three successful read tool calls**, no prior sources or argument errors. Native reads were a device-health snapshot, a hub-events query and a broad 100-row recent past-log page. The health tool returned **39 stale / 1 unknown / 211 total** under a 24h last-activity threshold. `lastActivity` only records a timestamp: it cannot independently show an actual communication loss, never-recovered session or physical outage.

The update and startup were directly observed in the hub event source, but the clustered device last-activity timestamps happened **after the startup** and other stale devices had later timestamps. The model nonetheless labelled the firmware event the **verified primary trigger** and interpreted similar timestamps as concurrent device reporting failures, without checking targeted device/driver history or MQTT connection state. Its sweeping assertion of no offline/disconnect logs was **unsupported**: the broad past-log call reported **14,816 matching records** but returned only the **newest 100 from a short period near the question**, not the previous day's startup window. This is a **source-window mismatch**, not evidence of no faults. Reviewer: **PARTIAL with significant historical-coverage and causality overclaims**. No device modifications or effective Write-denied credential verification occurred.

**Audit-only improvement candidate:** include successful bounded native `hub_get_logs` receipts in the private-first-answer scorecard using returned row counts, reported-more-than-returned flags and explicit `not_established` historical completeness. Scope can be detected for a native flat or gateway leaf. Flag failed, catalog-only or non-executed lookalike receipts without inflating evidence. Never emit private log text, parameters, device names/IDs or timestamps. Keep the `2.0.0-alpha.18` app version, Gemma/native MCP runtime, recorder, upstream server, V1 and permissions unchanged.

**Next general development gate:** With five source-reviewed domains showing different overconfidence/coverage failures, perform a **controlled fixed-source multi-domain model-vs-source-presentation comparison**, before adding any model prompt instruction or changing native tool routing. No automatic causal claim rewriting, no device-specific patch and no success inference from tool execution or CI. The existing frozen reboot question is an optional final independent baseline. Installed copy-button interaction itself remains to be confirmed separately.

### Daily-command source review and offline action receipts (8 November 2026)

Reviewed six private, installed-alpha.18/Gemma direct-device command first answers: one scheduler-related thermostat capability call, basic light ON/OFF, and two brightness changes. Six native device command tools returned accepted acknowledgments; **only four** of those responses had later successful independent same-device attribute reads. The last observed requested attribute matched in **three** and did **not match in one** (immediate ON request still reported OFF). A later separate read/event query showed a bridge-reported ON event, without establishing an exact physical-reporting latency. Two accepted actions had **no independent post-command read** in the original answer. User-visible answers in that subset ranged **3.970–10.775s**, median **6.252s**; context, tool count and command type differed. The two double-attribute dimmer cases were read-confirmed at the time of each query. This is an intentionally selected sample, **not** a model-wide pass rate or physical-actuation guarantee.

The same evidence shows the straightforward live model-led route already works with 2–4 native calls; the poor longer ON case required repeated nonmatching device-name searches. Avoid special aliases, automated command resubmission, a fixed waiting period or a mandated extra model round without cross-domain measurement. Source-verified outcome, efficiency and consent are independent gates.

**Implementation:** The private browser Technical JSON evaluator is extended to aggregate a new **v5 `action_receipts` block**: device-command acknowledgments vs native call attempts, embedded-state-snapshot counts, same-device subsequent fresh attribute reads, expected standard ON/OFF/`setLevel` attribute match/mismatch counts and explicit **human-review-required** outcome and **physical-effect-unverified** fields. All private values are kept inside the local evaluation process, never in report output; synthetically test false positives, stale state, contract failures and private-data leakage. This is **offline only**: installed build remains `2.0.0-alpha.18` and no runtime agent, tool schema, native MCP server, backup/permission, Hue/lighting, V1, HA or hub change is involved.

**Next phase:** Use the private scorecards and existing source-reviewed incidents to design a controlled, fixed-evidence **multi-domain action+investigation comparison**. Measure command/observation separation, completeness, causal uncertainty and latency together before changing the model or evidence presentation. User-supervised live write tests require explicit authorization, valid permissions and any device/system safety checks; repository test results are not write authorization. The UI's new `✓ Copied!` state was only tested in synthetic/Chromium CI; independent installed visual confirmation remains outstanding.

### Fixed-source multi-domain A/B experiment prepared (8 November 2026)

A new **offline-only** paired benchmark is in development on top of main commit e182f2fb5b6afce1a0dd8fba3ef5cfc837a32250. The private inventory contains **18** supplied Technical JSON exports, **10 with no prior context reported** (52 tool attempts), and **8 with prior context reported** (20 attempts). The available no-prior sample spans investigation and direct-action sources; two cases are comparable historical-humidity questions and many relate to the same household. It is a source-isolated starting set, **not** an independent or randomly sampled population.

The new tool freezes existing MCP response strings, native call order/status/arguments and the original question, constructs two A/B bundles per eligible export, and adds **only generic source-role notes** to one bundle. A hidden, balanced map allows blind human scoring of five evidence dimensions; source SHA-256 equality is checked before any aggregate comparison. The tool neither calls a model nor touches Hubitat, Home Assistant or MCP. It creates restrictive **private local** files, rejects output paths under the repository and never sends raw exports to CI/GitHub. Synthetic tests cover integrity, condition balance, missing answers/ratings, tampering, prior-context exclusion, source-role boundaries and privacy.

**State of evidence:** The 18 real exports have been inventoried locally, but there are **no run-and-rated model A/B pairs yet**. A small number of selected cases cannot justify a general model performance percentage or a runtime source rewrite. The next actionable gate is to run the existing Gemma model on both fixed-source variants in isolated, no-tools sessions and blind-rate each answer against private receipts. If source-role notes consistently help across independent domains with acceptable latency, only then consider a separately gated runtime change. Model-led native MCP operation and the external diagnostics recorder remain unchanged. Installed version stays **2.0.0-alpha.18**.

### Fixed-source evaluation execution gate (8 November 2026)

Actual private source preparation has now been performed locally: 18 historical
Technical JSON exports inventoried, **10 source-isolated cases** selected, 20
paired A/B files emitted and **10/10 pairs SHA verified** with balanced A/B
assignment. The eight prior-context-dependent exports are excluded from this
first frozen-source comparison. All historical MCP receipts were copied as
DATA, not replayed. The user-only private bundle was produced outside GitHub
and not uploaded to CI. **No paired Gemma inference or blind rating has yet
occurred**, so model-quality lift remains completely unmeasured.

A new optional standalone Ollama runner supports those prepared pairs with
NO default network activity and explicit private-source sharing consent.
Running a cloud model requires a separate cloud flag to acknowledge that the
locally hosted Ollama may relay the private MCP evidence to Ollama Cloud.
Each call is a retrospective **no-tools** chat, not a Hubitat/MCP operation;
answers are stored only in the user's private paired benchmark folder and
their human rating fields remain blank. The default request limit is two
pairs; a larger ten-case model trial requires explicit selection. The
experimental fixed-source release gate still requires blinded source
review across independent domains before any live-agent change.

No V2 runtime, model-prompt, source rewriting, response caching, timeout,
device routing, permissions, Heating Scheduler, Hue Bridge, Hubitat,
Home Assistant, V1 or diagnostics change. Version stays 2.0.0-alpha.18.

### Alpha.19 — Full-page Hub Diagnostics graphs (9 November 2026)

The user requested a **Pop out full page** option for graphs and supplied a Unified incident timeline screenshot with overlapping date/time labels near the right edge. Inspection of `hubitat-mcp-ai-v2/rootfs/app/ui.html` showed the main timeline SVG had a **fixed 860-unit viewBox**, but its X-axis tick count was computed from the CSS-displayed width; long date-bearing labels therefore overlapped. The detailed canvas also used width-based tick counts without adjusting for date label length.

**Implemented in the v2 UI:** separate new-tab focused pages for Unified incident timeline and Detailed metric history, preserving range/extent/layout/selected point or metric. The popup reuses local saved-recorder endpoints and draws the timeline at actual screen geometry, with improved label spacing. The detailed canvas becomes substantially taller. Return-to-dashboard navigation, responsive scrolling on narrow screens, and keyboard/pointer selection are retained. Source evidence remains read-only; no raw measurements/credentials are placed in URL parameters.

**Acceptance gate:** full browser checks for main page and both pop-outs (desktop/mobile), real event and CPU labels without collision, selected-point cursor, canvas size, alpha.19 UI/server version agreement, repository Python suite and container smoke. If any gate fails, do not merge or announce the new UI as installed. There are **no changes** to v2 native MCP tools, AI answer generation, Hubitat, HA, diagnostics recorder or V1. Existing alpha.18 continues functioning until the user updates the add-on.

### Alpha.20 — selected-area time zoom (9 November 2026)

User requested selected-area zoom in the full-page HomeBrainOS diagnostic graphs, similar to the Hub & Device Monitor app. Added one **read-only, shared time-window brush** for both the synchronized Unified incident timeline SVG and detailed Canvas metric plot. Dragging shades a horizontal interval, release zooms in, repeating narrows it; **Reset zoom** returns the complete requested range. A quick click still inspects a saved timestamp. SVG/canvas pointer coordinates respect viewBox, CSS scaling and pop-out/desktop dimensions. Browser keyboard access to observed time points remains intact, while Escape cancels a drag.

Applied the time window to both plots' data filtering and autoscale (not merely visual magnification). Source gaps and outage/startup markers remain evidence-scoped. Pop-out URL contains display-only time bounds, not any recorder sample data. Range or time-axis changes reset zoom; layout and metric changes keep the selected time window. No new API, polling, native hub read, model call, write or graph-data mutation. Zoom cannot restore raw readings that the API did not return in a downsampled window.

**Release gate**: alpha.20 UI/API/config alignment, synthetic JS tests, desktop/mobile browser pointer drags and reset in both popouts, full repository Python suite and container build; exact-head CI green before merge. No native MCP tool, AI prompt, Hubitat/HA, separate recorder service, backup or V1 modifications. Alpha.19 remains installed until user updates.

### Alpha.21 — Private benchmark evaluation workspace (9 November 2026)

Following the offline fixed-source PRs #1550–#1552, the user requested a
**no-PC, phone-only way** to run the previously prepared Gemma A/B test.
Implemented a separate third **AI Benchmark** tab in v2 with a bounded private
ZIP importer, manifest/source SHA verification, persistent add-on-local source
storage, explicit model/cloud consent gates, and asynchronous two-pair pilot
runs using the already configured Ollama model connection. The evaluator's
model payload contains only separate system/user messages, `temperature:0`,
`seed:42`, and **no `tools` list**; it cannot call Hubitat MCP or replay
device commands.

The same-origin UI displays A and B unedited as plain text, provides the
unannotated source receipts for blind human assessment, records five
user-supplied score dimensions and exports a **report containing only paired
aggregate statistics** (no private source, answer or assignment). Private
data can be explicitly deleted; a stopped run preserves already completed
responses. Server-side limits reject ZIP traversal, unexpected/encrypted
entries, symlinks, oversized/modified sources and unpaired conditions. One
imported dataset persists in /data across add-on restarts. Model calls incur
possible cloud costs and share private evidence **only after explicit
approval**. Import alone does not contact the model.

The original alpha.20 action-verification, chart popouts, zoom and V2 model-led
MCP behaviour remain unchanged. No native MCP, heating, Hubitat, HA,
recorder, permission, backup or v1 modifications. Tests cover malformed
source bundles, failed/forbidden approvals, no native tool list, saved answer
integrity, blind scores, privacy-safe report and Android-size browser UI.

**Acceptance:** validate alpha.21 UI/API/config agreement, exact-head unit/UI
tests, desktop/mobile Chromium, full Python suite, container smoke and
post-merge CI. Neither synthetic tests nor the new page constitute a completed
Gemma A/B evaluation. Actual cloud-run and human blind scores still require
the user's explicit action.


### Alpha.22 — Isolated synthetic autonomous first-answer milestone

The user completed the 10-pair private A/B Gemma fixed-source benchmark.
The net generic annotation effect was a small negative (~3 points across 46
applicable ratings), with three baseline wins, three annotation wins and four
ties. Duplicate humidity history and assistant-informed human scoring limit
interpretation. No general benefit was established, and no change to live
reasoning/device control was approved or performed.

To assess an untested dimension—**tool selection and follow-up evidence
retrieval by the actual v2 model-led agent**—added an independent, synthetic
\`Autonomous Lab\` tab. The model receives fictional scenarios, chooses
native-shaped MCP gateway tools via the unchanged production
\`Agent.answer\` loop, and independently decides when to stop. A separate
\`SyntheticMCP\` instance always serves tool discovery, reads and up to one
allowed **memory-only simulated command** for command cases. No call can
reach Hubitat or HA, and no prior private A/B source is imported or sent.
Other action attempts and duplicate commands are blocked and counted.

Six independent fictional domains cover successful and unsuccessful
commands, historical heating demand, schedule/trigger causality, stale
telemetry, and state-event reporter versus command-issuer attribution.
A visible checklist reports exactly which expected tool-source classes
were retrieved, **not whether the answer is true**. Manual 0/1/2/n/a
ratings assess grounding, completeness, causal calibration, command
outcome and usefulness. Export omits prompts, sources, answers and keys;
it includes cases, tool-round counts, retrieval coverage and manual scores.
Evaluations are user-initiated, capped at eight model rounds, 24 tool
attempts and a 90-second deadline, with clear cloud-credit consent.
No independent live inference or physical-effect claim is supported.

Version: \`2.0.0-alpha.22\`. Tests use synthetic model transport and
in-memory MCP fixtures only; no cloud requests, device actions or HA
config mutations. Native Ask/Chat, earlier private A/B scores, recorder,
graphs and V1 remain untouched. See
\`docs/HUBITAT-MCP-AI-V2-AUTONOMOUS-LAB.md\` for operation, limitations,
rollback and scenario details.


### Alpha.23 — Autonomous Lab: live synthetic-run contract correction

A user-installed \`2.0.0-alpha.22\` Gemma trial reached the evaluation's
8-round cap with 10 rejected synthetic tool attempts and no simulated
command or fresh follow-up verification. The synthetic tool adapter had
drifted from the real MCP Rule Server tool schemas. The root *possibility*
is clear from code (native \`parameters: ["40"]\` versus the old simulated
\`params: [40]\`, invented gateway names, absent discovery-cache
semantics); the per-call causes remain unverified without the preserved
original tool receipts.

Corrected the synthetic MCP adapter to mirror native gateway placement,
real command parameter naming, on-demand leaf schema discovery and
validation. The production \`Agent.answer\` and native MCP connection
remain unchanged. Added machine-readable rejected reason codes; the
sandbox retains its memory-only, single-command safety envelope. The
evaluation budget is 12 model rounds / 40 synthetic calls / 120s rather
than solely lifting the cap to mask invalid tool contracts.

Critically, unsuccessful model/transport outcomes are no longer counted
as answered/gradable cases. An explicit, newly approved retry of **only**
a failed case archives the prior failed attempt (up to two retries) and
preserves other cases. UI and report distinguish answered, failed, graded
and prior failed runs. New synthetic regressions verify native string
\`parameters\`, reject old \`params\`, progressive schema discovery and
safe retry with original failed-result preservation.

**Operational:** upgrade only the v2 add-on to \`2.0.0-alpha.23\` and
retry \`lab-01\` with consent. Inspect actual synthetic tool receipts
and coverage before judging Gemma; do not infer live device performance.


### Alpha.24 — Downsampled diagnostic trace continuity (chart only)

After reviewing the 9 Nov three-day Unified Incident Timeline screenshot
(3,409 external OS-memory observations and 332 distinct native 5m CPU samples),
the disjoint vertical memory strokes were traced to a frontend/backend
sampling-contract mismatch. `summarize_history_samples` keeps actual
first/last/min/max readings when the raw return exceeds 3,000 observations,
and gives retained samples a `diag_segment` ID that changes on failed
probes or genuine cadence gaps. Both SVG and canvas renderers previously
applied raw source-cadence thresholds even to the downsampled rows, turning
legitimate reduced-data spacing into visual breaks.

PR #1558 changed the renderers to join selected points **only within
the same known segment when `downsampled=true`**, while continuing to break
on segment changes and retain strict time-based checks for raw or old
unlabelled data. The 9 Nov chart screenshot was not a live proof that all
intervals were healthy, and no causal inference is made from the line shape.
Synthetic UI regression tests verify SVG/canvas continuity, real gaps,
native and external thresholds, and missing segment metadata fallbacks.
PR #1558 passed the v2 pilot tests, repository validation and release
assurance, and merged as `be90ab12` on 9 Nov 2026.

**Release:** `2.0.0-alpha.24` makes the change installable via the v2 add-on
version update. This release does not modify the external recorder's
historical SQLite observations, probes, any hub/device, MCP connector,
autonomous synthetic lab or V1. Check the newly installed version,
refresh the timeline and visually confirm that confirmed gaps remain blank.
Live installed acceptance is still outstanding.


### Alpha.25 — Blinded holdout reasoning-quality experiment (9 Nov 2026)

**Basis for experiment:** The first six live-Gemma-on-synthetic autonomous
MCP evaluations (all graded) achieved 19/22 expected read-source checks
(86.4%) but only 34/52 manual evidence-quality points (65.4%), with
causal calibration 5/12. This is an exploratory signal, not a reliable
population performance statistic. Earlier 10-pair frozen-source annotations
also did not show a clear advantage over baseline.

Built an opt-in **Reasoning A/B** tab and a new 6-case fictional holdout bank:
power readings versus supply outage, entrance light provenance, humidity
sample intervals, multi-zone historical heating, independent stale sensors
and accepted-but-unverified beacon command. These are separate from both
earlier benchmark datasets, not patches targeted to their exact questions.

For each holdout case, identical model configuration and source fixtures
run twice in separate \`Agent.answer\` loops, starting from empty history
with completely fresh \`SyntheticMCP\` state. Baseline retains the
existing alpha.24 system skill. Candidate has **one additional, general
evidence-completion system instruction**: consider discriminating evidence
for causal claims and unresolved alternatives before stopping. It does
not select tools, add forced reads, restrict writes, or change the
production agent. Randomised A/B assignment is stored only in a private
\`/data/homebrain-v2-reasoning-ab\` file. The report remains blinded until
**all six pairs have successfully run and been manually scored**.

Per-arm receipts and checklists distinguish model calls, retrieved
sources, **client schema validation errors** and simulator rejections.
The same client-versus-simulator distinction is now added to the
original six-case Autonomous Lab dashboard and JSON reports, without
touching its saved responses or scores. Pair status is resumable after
stops, failed attempts can be explicitly retried, successful answers
remain unchanged, and no automated real-device actions occur. Reports
omit raw answers, source receipts, identifiers and credentials.

**Version:** \`2.0.0-alpha.25\`. Read
\`docs/HUBITAT-MCP-AI-V2-REASONING-HOLDOUT.md\` for six scenarios,
operational steps, blinding limits, evaluation interpretation and rollback.
No model traffic is generated by code review or CI. **The installed v2
add-on must be updated and the user must consent to the paired model runs
before Gemma is actually evaluated**. No production tool/skill changes
should be promoted based on this small synthetic study.


### Alpha.26 — prospective A/B scoring integrity (9 Nov 2026)

**Trigger:** Code inspection of the merged alpha.25 holdout found that
\`ReasoningExperiment.score()\` accepted repeat submissions to the same pair.
Because the aggregate report reveals the candidate/baseline allocation after
all six pairs are scored, this permitted silent post-unblinding revisions of
previously labelled *blind* ratings. The browser also kept Save enabled for
already-rated cases. This is an evaluation-integrity fault, not a Gemma
reasoning result.

**Fix:** Each pair's first saved A/B rating is now immutable; the backend
rejects re-submission, the UI preserves values visibly in disabled selectors,
and Save is disabled after submission. Unit tests exercise pre- and
post-unblinding rejection, API duplicate score rejection and desktop/mobile
browser locked controls. The only reset remains the existing explicit full
Reasoning A/B study delete. Existing saved ratings remain readable, without
migration, re-grading or altered mapping.

**Version:** \`2.0.0-alpha.26\`. Baseline/candidate prompts, six fictional
holdout scenarios, order allocation, source receipts, isolated model/tool
invocation, Hub Diagnostics, native MCP, and production AI remain unchanged.
The six paired live-Gemma runs have **not** been supplied or validated;
there is no evidence yet that the candidate improves causal calibration.
Do not promote its guidance into production based on mocked CI or the
previous six-case autonomous benchmark. The next user-run step is to install
alpha.26, run the already prepared six blinded paired evaluations and submit
the completed aggregate report for source-aware assessment.
