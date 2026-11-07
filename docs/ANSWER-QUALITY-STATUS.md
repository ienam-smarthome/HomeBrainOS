# Answer Quality — active status and cross-chat handoff

## 2026-11-07 — Current development audit and privacy-safe shadow capture

Reviewed main `070f6f9b19248868ef4d44096425629b9cab2b9f`, permanent direction, current claim integration, evaluation tooling, recent merged work and all three open PRs. [Development review](DEVELOPMENT-REVIEW-2026-11-07.md) records priorities and limits. Independently verified all four required workflows passed on #1514 head `33d9d911377cb76c9a8fabcec56c25deaceca132`. Installed v0.18.455 acceptance remains pending; the user's supplied summary adds no new installed test or full source JSON.

**Evaluation tooling gap corrected:** `answer_quality_capture.py` previously omitted the entire new shadow sidecar. Add a privacy-safe summary distinguishing missing, invalid and provided diagnostics; rejection-status presence; strict reported booleans; and two allowlisted focal-source labels. No raw status/reason strings or source payloads, automatic quality score, live calls or production behavior. Version remains 0.18.455. Local compilation and a standard-library smoke check passed; exact-head required PR CI must pass before merge. Next: full installed acceptance JSON, then frozen cross-domain model-proposed typed claims and independent source review before publication promotion. Original controller, first attempt and deployed SHA remain unverified.

---

## 2026-11-07 — v0.18.455 source-attested causal shadow merged; installed acceptance pending

**User's complete first live response** (7 Nov 10:54–10:55 GMT, v0.18.453, 8 evidence receipts, 7 model rounds, 39.0s elapsed): Reported OFF at 2026-11-07 00:30:00.023 GMT by Matter Hue Bridge Pro, previous reported ON at 20:58:15.909 on 6 Nov, recorded duration 12,704s. A **real global hub past-log request** covered the focal time (23:50–00:40 GMT), returned 0 rows out of a broader source scope reporting 12,945 total rows, with no historical completeness established. A second hubEvents request also covered the same time. The command-off native history returned 7 events, but none was within two seconds before the focal OFF; the full device history returned 11 switch rows including 6 OFF reports (2 with adjacent `button 2 pushed` commands within the two-second matching convention). Source-specific app/rule execution was **not** independently verified; no direct sensor history requests occurred in this turn. The answer's top-level initiating controller status was appropriately unverified. However, 'these listeners did not initiate it' was an unsupported negative; the enumerated 'likely' external possibilities were not evidence-backed or ranked. **No `evidence_validation.claim_evidence_shadow` appeared, despite deployed version 0.18.453.** `investigation_coverage` exposed only model-proposed `hypothesisComparisons`, not `domain=causal_provenance`; the optional `homebrain_causal_secondary_correlation` was never called. These two *independent* gates silently skipped the intended claim adapter.

**General architectural fix candidate v0.18.455 (main already at v0.18.454 for independent graph work):** For an explicit read-only **latest-OFF causal** question with a single targeted ID, let the source adapter attest focal time from the **latest source-reported OFF in successful native-derived device history** when optional correlation is absent. Require target label in the submitted question, explicit question-scope intent, source state witness, unique identity and read-safe receipt; reject missing/ambiguous scope. Record `focal_source=source-history-latest-off`. Allow the full host packet to activate existing final API causal provenance checks even when `investigation_coverage.domain` is absent; preserve explicit-domain legacy routing and all write/confirmation boundaries. Expose `evidence_validation.claim_evidence_shadow` for an attested causal packet and an allowlisted status when an attempted latest-OFF packet is unverified. Extend the generic downstream-listener guard to correct 'listeners reacted; they did not initiate' negatives without claiming the opposite. No new model/MCP reads, devices, billing changes or complete history assumptions. `model_claims_assessed=false` remains mandatory. Test against realistic v0.18.453 attachment-shaped source evidence, not only a correlation fixture.

**Merged CI:** [PR #1514](https://github.com/ienam-smarthome/HomeBrainOS/pull/1514) passed all four required workflows at exact tested head `33d9d911377cb76c9a8fabcec56c25deaceca132`: Release assurance (6,747 passing Python tests, two nonblocking warnings, add-on container smoke and metadata), Hubitat MCP AI tests, Validate HomeBrain OS, Answer Quality scorecard integrity. Squash-merged to main as `adf9e5ca1ff046ca85c8687d5b4010e9bb8c76fc`. **Installed source-real v0.18.455 acceptance remains pending**, and neither actual first-attempt deployment SHA nor original historical cause has been verified. A returning shadow receipt is a coverage-integrity milestone, not proof that an upstream controller was identified or that every model-authored speculation was eliminated. Continue frozen cross-domain claim publication roadmap.

---


## 2026-11-07 — v0.18.453 trusted claim-evidence response adapter merged

**Claude review:** The user provided a ZIP with revised `claims_v2.py` v2.1, `evidence_adapter.py`, a condensed fixture and 21 passing local tests. Independent review of the entire 7 November Technical JSON confirmed that the four app-log queries were for older ON-related intervals rather than the focal 00:30 OFF; the Historical Journal FP400 `inactive` timestamp is collector reception and both independently verified native focal sensor windows returned zero events. The source-returned OFF sample had six state transitions and two recorded command-off matches under a two-second matching rule; four had no matching command in those **returned records**, not evidence of an external cause. Four of ten sensor candidates were marked selection-stage `probed` but only two successful direct history-window queries were recorded. Claude's validator accepted several fail-open cases on these sources (zero checked pages, invalid command clocks, duplicate model-selected transitions, failed reads) and was **not** used to replace the canonical contract.

**v0.18.453 architectural candidate:** Extend the existing `claim_evidence_contract.py` with host-controlled whole-sample `transition_pairing`, quarantined `journal_observation` and focal-time-scoped `absent_in_scope`. Add `claim_evidence_adapter.py` that reconstructs typed events only from successful read-only receipts, selects an unequivocal host focal event and targeted device identity, deduplicates native history projections, and never confuses logged reception with sensor source time. Give read-only causal `/api/ask` outputs a compact `evidence_validation.claim_evidence_shadow` diagnostic: true bounded sample counts, separate 4/10 candidate probe and 2 native sensor window checks, and count of actual log request windows containing the focal event (0 of 4 in the historical response). The metrics declare `shadow_only=true`, `model_claims_assessed=false`. No extra MCP/model calls, publication rewrite or device changes. Test source-neutral fixtures for causal lights, heating, humidity, power and hub-health source-role boundaries. Existing v0.18.452 failed-repair deterministic floor is unchanged.

**Merged verification:** [PR #1511](https://github.com/ienam-smarthome/HomeBrainOS/pull/1511) passed all four mandatory workflows on exact head `1600af59001959d37e3e86b79aa7db4931b32efd` (Hubitat MCP AI tests; Validate HomeBrain OS; Release assurance including **6,738 passing Python tests** and packaged add-on smoke; Answer Quality scorecard integrity). Squash merge main commit: `755635e8fb08d8f976504a3f55ef145d21a30c6c`. **Installed source-real v0.18.453 live acceptance is pending**; CI validates synthetic source roles and runtime safety only, not actual first-answer quality. Continue existing read-only OFF question and inspect `evidence_validation.claim_evidence_shadow` for `focal_attested=true`, `shadow_only=true`, `model_claims_assessed=false`, distinct candidate probed/native windows, and bounded command/log coverage. If retained history evolves, counts may legitimately differ from the 7 November evidence packet.

---


## 2026-11-07 — v0.18.452 generic repair floor merged; live acceptance pending

**Read-only installed evidence:** User supplied the full v0.18.451 natural-language OFF explanation and 19-receipt Technical JSON at ~10:05 GMT. The factual OFF boundary (2026-11-07 00:30:00.023 GMT), Matter Hue Bridge Pro state-reporter role, bounded command-off records (7 returned; latest at 2026-11-06 20:53:25.307), preceding ON boundary (2026-11-06 20:58:15.909), recorded 12,704-second ON-state interval and unknown upstream initiator were correctly represented. However, the answer **incorrectly placed FP400 motion=inactive 19 seconds before OFF as a verified source sensor event**: the sole FP400 Historical Journal row was at collector reception 00:29:41.617 and both verified absolute native sensor history windows (FP400 motion, Seeed presence) returned **zero** source event rows. This cannot establish source sensor-event timing. The answer also claimed app past-log searches for Lights Off and Google Home returned zero entries in the window surrounding focal OFF, but those app-specific requests were at **2026-11-06 15:13** (an old interval). A separate device-specific past-log window was at **20:58 ON**, not 00:30 OFF. Therefore no focal app-log query was verified. It weakly suggested an external action without independent evidence. Technical JSON: version 0.18.451, gemma4:31b, 9 model rounds, 19 tool calls, 49.346s elapsed, 2 synthesis validation issues, 1 failed synthesis repair; evidence_validation showed no corrections. request_provenance.first_attempt_verified=false and deployed_build_sha_verified=false: do not claim full first-attempt deployment attestation. Overall **failed source-real acceptance** despite a better top-level uncertainty verdict.

**General correction candidate v0.18.452:** Rather than another light/motion-specific regex, use a **claim-validated deterministic factual floor when synthesis repair fails**. Code gates to non-confirmation read-only causal_provenance latest-OFF investigations with rootCauseVerified=false, a unique host correlation requestedBoundary, and independently returned source switch history. It constructs only host-authored `observed_value` and `observed_interval` claims checked by the v2 validator. The final answer uses typed bounded command receipts, verified source-clock sensor events, separate collector-reception archive observations, and checks the actual date windows of returned app-log requests. It never republishes the failed model's prose, assumes a missing command is globally absent, or promotes a bridge reporter/listener to issuer. If the focal evidence does not meet requirements, it leaves the existing guarded answer path unchanged. No additional model/MCP reads, billing switch, write path, confirmations or device modifications. Claimed improvement limited to the failed-repair floor: general claim-first publication and frozen cross-domain quality scoring are **still pending**. **Merged CI proof:** [PR #1509](https://github.com/ienam-smarthome/HomeBrainOS/pull/1509) passed Hubitat MCP AI tests, HomeBrain validation, Release assurance (6,727 Python tests + smoke/metadata), and Answer Quality scorecard integrity on the same exact tested head `07b40c87af6834e45ebcdbe22daea32d9786f629`. Squash merge main commit: `6b858876b127340cf41602fcbfe3f5ee92184510`. **Installed v0.18.452 source-real test is still pending**. Do not conflate synthetic CI with demonstrated first-answer improvement.

---


## 2026-11-07 — v0.18.451 generic claim-evidence shadow core merged

**External review and supplied draft:** The user supplied Claude's original `claims_v2.py` and `test_claims_v2.py` drafts; all 13 provided standalone tests passed. Review against current main `6264be5` confirmed `causal_claim_attestation.py` (narrow V1 shadow attestation), `causal_witness_ledger.py` (source-attested ledger V1), and `causal_claim_publication.py` (one narrowly eligible claim-guided incident path) already exist. Therefore do not create a parallel live causal engine or claim that existing code was universally shadow-only. The v0.18.450 PR #1505 is merged with all four exact-head checks green; repo notes had stale candidate CI wording. **Installed v0.18.450 acceptance is still pending**.

**Security/quality gaps in the submitted draft:** A zero-page source could attest `absent_in_scope`; source-command timestamps were not checked; listener pairs could be used as switch operating intervals; naive/aware clocks could throw; model-selected `scope=context` bypassed focal identity; free-form `what` could inject arbitrary negative claims; the v1 adapter copied incompatible `state-report` / `issued-command` roles and did not recover switch values. The 13 passing tests do not establish safe live publication.

**v0.18.451 development increment:** Introduced `claim_evidence_contract.py` with generic source-role/command distinctions, strict source-offset clocks, exact data values, fail-closed focal and trusted context scope, real v1 `event_class` + role translation, verified native absolute-window zero-match coverage admission, finite same-unit arithmetic, valid reported intervals, and a pure `assess_claims_shadow` function returning only counts and allowlisted reason codes. Adapted the supplied baseline tests and added adversarial tests against the above failures, including listener/command roles and negative-history claims. This is **an offline shadow-only library**: there is no new live model prompt, model round, MCP read, runtime publication/repair replacement or device action. The existing regex guards remain until frozen matched-evidence quality tests justify retirement.

**Merged validation:** [PR #1506](https://github.com/ienam-smarthome/HomeBrainOS/pull/1506) passed all four mandatory workflows at the exact final PR head `c0f015ea2aeb55fd4ec1913fa01e915710269bbd`, including 6,720 passing Python tests, add-on container smoke, repository validation, Hubitat MCP AI tests and Answer Quality scorecard integrity. Squash merge landed on main as `900243183915d98510a8b9f11fa51dd30328095d`. The first CI cycle failed only repository hygiene because the submitted filename `claims_v2.py` used a banned runtime version suffix; the canonical published module is `claim_evidence_contract.py`, and the second full CI cycle was green. No source-real first-answer uplift or model-to-model quality result has been measured. Next: confirm installed v0.18.450/451 baseline through a fresh read-only question with full Technical JSON; transport trusted event focus plus claim envelopes through a non-publishing observation checkpoint; then freeze cross-domain evidence packets and compare claim-vs-legacy accuracy, downgrade and usefulness without per-incident patches.

---


## 2026-11-07 — v0.18.449 installed acceptance failed (read-only); v0.18.450 candidate

**Source-real verification:** User supplied complete v0.18.449 HomeBrain Ask Technical JSON for the same most-recent light OFF question at 08:42 GMT. Last reported ON was 2026-11-06 20:58:15.909 GMT, with typed `command-on` at 20:58:15.775 from SenseCap D1 Settings (134 ms before reported ON); last reported OFF was 2026-11-07 00:30:00.023 GMT, ending a 12,704-second recorded switch-state interval. Focal FP400 Computer Desk motion=inactive was independently read in a successful bounded MCP event window at 00:29:40.936 (19.087s before OFF) and also appeared in a partial Historical Journal receipt with collector-reception time. These are correlations, not proof of the OFF initiating action. Seven old `command-off` receipts had their latest recorded occurrence 20:53:25.307 the previous evening, issued by the button-rule app; none matched the 00:30 OFF. This is not proof that no Hubitat-side action occurred: sourceHistoryComplete=false, the app configuration read for app 4020 failed, historical logs were bounded/incomplete and upstream-origin/device logs were not verified. The focal triggered[] apps were listeners to the OFF event, not proof that they were or were not initiators through a separate route.

**Failed final answer:** Despite correctly reporting unresolved origin and a concise timeline, the v0.18.449 output asserted "no record of a command being issued by Hubitat" without limiting the claim to checked pages, and said the bridge's physical state report "indicates the action occurred outside of Hubitat's control." It described the single native `motion=inactive` event as "activity", imported an irrelevant 15:13 prior-interval controller warning, and declared notified apps listeners "rather than triggers" as if source roles exclude independent initiation. The Technical JSON reported 7 model rounds, 20 tool calls, agent 43.8s, 48.2s elapsed, unresolved, 3 synthesis issues and 1 failed synthesis repair. None of the v0.18.449 API correction flags appeared. This is **a failed single live acceptance**, not a measured model benchmark or verified external OFF cause.

**General v0.18.450 candidate:** Tighten source-inference guard to catch reporter-to-external leaps and broad "no record of a command being issued" statements, retain positive switch reports; do not equate listener notification with proven negative initiation. Restrict old controller-boundary explanations to the uniquely requested OFF timestamp when host correlation is present; don't invent a historical interval. Introduce source-neutral sensor-value precision backed by matching focal correlation and native absolute-window event timestamps, not journal reception or an unknown sensor; wire it to synthesis and final read-only publication. Synthetic regression tests preserve exact sensor state and typed positive command facts with write/confirmation exemptions. **Candidate CI and installed acceptance are pending**. No changes to Hubitat, HA, devices, billing selection, watchdogs or permission model.

---


## 2026-11-07 — v0.18.449 focal-source proof correction merged; installed acceptance pending

**Live installed evidence:** v0.18.448 was confirmed through a read-only HomeBrain Ask result, with six Gemma cloud model rounds, 16 tool calls, roughly 35.6s elapsed and outcome=unresolved. The most recent switch OFF report was at 2026-11-07 00:30:00.023 GMT. A reporting bridge is not a verified initiating controller. A recorded command-off from an earlier boundary does not establish a matching command at the latest boundary, but incomplete command history also cannot establish that the latest cause was external. The response wrongly asserted definite external origin and no Hubitat instruction, described a source-observed motion=inactive event as generic activity, and referred to an app listener that was present on an older event but absent from the focal triggered[] list. Focal source integrity and upstream origin remain unverified. The repeated-long-prose bug did not reappear. This is one source-reviewed failure, **not** a measured production accuracy rate.

**Merged implementation:** [PR #1503](https://github.com/ienam-smarthome/HomeBrainOS/pull/1503) passed all four mandatory workflows on exact tested head `dcf50f86381f959c9cde8eda5287f1da27d08a34` (Hubitat MCP AI tests, full Python suite/add-on smoke through release assurance, repository validation, and Answer Quality scorecard integrity), and squash-merged into main as `5ff4c1127b54a85afc7b5c53386dd4e8e97d0980`. First candidate CI failed five older regression tests; the final changes preserved those earlier source-bound invariants, then passed the complete second CI cycle. The source-neutral v0.18.449 code reconstructs focal ON/OFF from typed receipts, binds app listeners to a verified focal clock, rejects unsupported external-control/no-command certainty after synthesis, and teaches precise sensor-event values. Technical JSON only records applied corrections. No model provider, watchdog, paid route or write/confirmation policy changed. These are code-level safeguards, not verified first-answer improvement.

**Next acceptance:** Installed v0.18.449 verification remains pending. After updating the add-on, run one held-out natural-language read-only investigation with complete Technical JSON and grade focal event/command/listener scope, exact sensor values, unsupported conclusions and preserved timeline. Do not call a repaired final answer proven if synthesis still fails or upstream source receipts are missing. No live Hubitat/HA/router state was modified by repository development; rollback the merged change if new evidence shows suppressed verified facts or altered write/confirmation strings.

---


## 2026-11-07 — v0.18.448 generic causal-answer repetition and proof-boundary guard (merged; installed verification pending)

**Held-out read-only test:** The installed HomeBrainOS v0.18.447 Livingroom Light 2 investigation reported a focal OFF at 2026-11-06 20:53:25 GMT and later ON at 20:58:15 GMT, while classifying the bridge as state-report producer and SenseCap D1 Settings as a downstream listener rather than a proved OFF initiator. The visible output duplicated the same source-role narrative multiple times, mixed an unsupported or at least unattributed assertion that an OFF command was recorded into its log-coverage note, and did not establish a definite upstream OFF initiator. These are **displayed-answer observations only**; full Technical JSON source rows and command issuer receipts were not supplied for this test. No new cause or decisive command proof can be inferred from the screenshot or text.

**Merged implementation:** [PR #1500](https://github.com/ienam-smarthome/HomeBrainOS/pull/1500), exact tested head `32583016a90719d63d3da2ec07d22841a3f87bd0`, passed all four mandatory CI workflows (Hubitat MCP AI tests, full Python suite and add-on smoke through release assurance, repository validation, Answer Quality scorecard integrity) and squash-merged to main as `dec163afae4664ae742a2f6258713293725643c7`. Implemented: Add a final, section-scoped exact-long-sentence presentation deduplicator after existing factual claim guards in `api_response_builder`; keep independent claims, headings, lists, tables, code and distinct timestamps, and exclude all writes/confirmation replies. Emit `evidence_validation.repeated_long_prose_removed` only when true. Add general system prompt proof rules distinguishing actual typed `command-off` source events from bridge-reported `switch=off`, downstream `triggered[]` listeners and empty app logs. A model may not claim an OFF command was recorded without target-matched source evidence. No special-case app/device IDs or increased tool caps. The current source-specific event causality **remains unverified** without complete Technical JSON.

**Verification:** Nine general offline regression tests and all four mandatory CI workflows passed on the tested head, including full Python suite, release assurance and add-on smoke. This proves the code-level dedup and write-approval exemptions, **not** that the model identified an OFF cause or that its original claimed command record was supported by complete evidence. The deployed v0.18.448 add-on and natural-language uplift remain unverified. After installation, run a fresh held-out read-only cause question with full Technical JSON; keep reported-state, command event and initiator causation separate. Do not mistake a clean answer for proof of historical source completeness or measured general answer quality.

---

## 2026-11-07 — v0.18.447 raw-versus-observation span clarity merged (live re-test pending)

**Held-out live trigger:** The installed v0.18.446 Bedroom 1 TRV history response retrieved 204 raw Hubitat device events across 5 paged read-only source requests but only 11 `temperature` observations (20:30:52–00:06:35 GMT, 3h36m); observed endpoint change was +0.2°C. The answer inaccurately said "only approximately 3 hours and 36 minutes of history were retrieved" as if matching temperature observations represented all raw fetched history. The trace separately showed `sourceEventCount=204`, `analysisEventCount=11`, `sourcePagesFetched=5`, `sourceWindowBoundaryReached=false`, `sourceCoverageStopReason=older_source_page_short` and `historySourceIntegrityVerified=false`. No evidence establishes full 24h retention, sensor failure or long-term stability. The v0.18.446 hub-local GMT display and independent pagination both worked.

**Merged implementation:** [PR #1498](https://github.com/ienam-smarthome/HomeBrainOS/pull/1498) passed all four required CI workflows at exact tested head `788bd5faa9a3b26404f59258ee8ab30e21f40e9f` (full Python suite, add-on smoke, repository validation and Answer Quality scorecard integrity) and was squash-merged as `7d1a4dcfef333d345ed1cda5f78dbf2b90b91adc`.  The history adapter now reports a separate `sourceEventRange` (earliest/latest raw fetched event dates and raw span), `sampleBounds.spanSeconds` (earliest/latest selected-attribute observation span), `sampleBounds.timestampedCount`, plus a host-generated `sourceCoverageNarrative` distinguishing those scopes, lookback, page count and stop reason. The existing evidence projector retains these source-qualified fields and a generic AI presentation policy disallows treating the matching-sample span as total retrieved history. Zero/one timestamped sample is not misrepresented as a zero-duration measurement. No extra MCP calls, model provider changes, paid routing, device control or write permissions. This is a general quality improvement, not an incident-specific text rewrite.

**Verification:** Offline regression cases covering mixed raw and matching attribute spans, zero/one sample non-interval, explicit source range and evidence projection passed with all four required CI workflows. Installed v0.18.447 deployment and natural-language wording uplift remain NOT VERIFIED until a fresh source-real history question. Next separate acceptance test: user runs read-only most-recent Livingroom Light 2 OFF incident investigation (device events, actual command issuers, app configuration and logs where available); no causal certainty without producer/trigger evidence. Do not modify any devices.

---

## 2026-11-06 — v0.18.446 timezone and history coverage merged (live acceptance pending)

**Live evidence basis:** On v0.18.445, Bathroom Meter history read returned 11 humidity observations. A 74% reading at 14:25:04.678 +0000 preceded a 59% reading at 18:26:04.288 +0000, about 4h 1m between reported events. Three successful reads, two model rounds, 9.5 seconds; no paid route. This supports the observed calculation but not complete retention, exact physical crossing, proven first-attempt provenance or the new deadline beyond 180 seconds.

**Held-out TRV gap:** Bedroom 1 TRV history read returned only three temperature readings (each 22.2°C at 22:30:53, 23:00:53, 23:30:52 +0000), from a capped 50-row mixed event page for a requested 24h window. A zero difference among returned samples is verified, but a constant temperature over 24h is not. This response was 14.8s / three tool calls / three model rounds. November +0000 is GMT for the UK, while summer dates use BST; source should provide hub-local timezone labels rather than assuming UTC means the user wants UTC.

**Merged implementation:** [PR #1496](https://github.com/ienam-smarthome/HomeBrainOS/pull/1496) passed all four required CI workflows on exact tested head `2554db9dd061ff29559c8815176dcc0b9702a071` (full Python suite, add-on smoke, repository validation and Answer Quality scorecard integrity) and was squash-merged to main as `97c28a8d13b0f801112301b0886f20f2d219c5d2`. Model-planned reads now ask the hub's authoritative IANA timezone, convert event display labels without changing source timestamps, and extend saturated 50-row mixed pages by read-only native until bookmarks until the requested boundary or a truthful operational stop. Explicit source-page, sample-bounds and coverage metadata prevents treating fetched row counts as all retained events. A finite 1000-row resource guard remains. Exact-hour/source integrity, real upstream bookmark behaviour, and deployed add-on version require source-real validation. No hub, HA, router, devices or paid provider changed.

---

## 2026-11-06 — Fixed 180s investigation deadline removed (v0.18.445 merged; live verification pending)

**User instruction:** Original exact wording: "Proceed with the development plans (remove any existing limiters) and write to the notes." Follow-up clarified that the 180-second hard-total investigation deadline had **not** been removed in v0.18.443/444. The accepted direction is adaptive, evidence-progress-based read-only execution, not unlimited uncontrolled calls.

**Implemented and merged:** [PR #1494](https://github.com/ienam-smarthome/HomeBrainOS/pull/1494) passed all four required CI workflows on tested head `f4d19e10974949a7b81aa9d3ad995dd49b3a954a`; squash merged to main as `6047ab28f3f947f226d71b9533ec1910b597d118`. Replace `_answer_result` normal-investigation `deadline_seconds=180` with `idle_timeout_seconds=180`, resetting only after a distinct successful source-scoped read receipt; and an independent emergency watchdog default of 1800 seconds. Preserve `RequestCoordinator.run(deadline_seconds=...)` only as an explicit compatibility/test mechanism, not normal Ask routing. Failed/duplicate/mutating receipts and UI/model-stage updates never renew the idle timer. Keep bounded evidence-only cancellation results, HTTP 504 diagnostic fallback, per-model/tool timeouts, provider cost policy, permissions, confirmation, disconnection/superseding cancellation and the existing 18 outer tool-round emergency ceiling. Keep deprecated `investigation_deadline_seconds` option at 0 for upgrade compatibility; previously saved 180 must not be used by normal Ask. This is a general source-progress gate, not an incident-specific patch.

**Verification:** The repository's synthetic regression tests, full Python test suite, add-on container smoke, validation and Answer Quality scorecard checks passed. These verify code paths, including distinct successful-read continuation, duplicate/failed/write read stopping, stage chatter, hard emergency watchdog, progress privacy and legacy deadline compatibility, not source-real first-answer improvement. The installed Home Assistant version/options and any independent ingress/proxy/provider timeout remain **NOT VERIFIED**; no live first-answer uplift is claimed. Device history, source sufficiency, pagination and Phase 2 deterministic arithmetic-to-MCP integration remain separate outstanding milestones. No live HA/Hubitat/router change.

---


## 2026-11-06 — Phase 2 deterministic observed-time-series foundation (v0.18.444 merged; live acceptance pending)

**Implementation scope:** New source-neutral `hubitat-mcp-ai/rootfs/app/observed_time_series.py` and `tests/test_observed_time_series_phase2.py` on `feature/autonomous-phase2-observed-series-core`. This offline operator can select a first/last reading satisfying a generic numeric predicate and the first strictly *later* reading satisfying another predicate, calculate the interval between **recorded samples**, reject invalid/non-timezone-aware samples, and report missing readings without claiming historical absence. The code explicitly sets `source_coverage_verified=false` and `exact_physical_crossing_verified=false`. No Hubitat, HA, router, MCP tool invocation, installed add-on, write permission or paid route was changed. New package version v0.18.444 is required by the runtime-file release gate even though production orchestration is unchanged; the source-real v0.18.443 acceptance remains pending.

**Verification and limitations:** [PR #1492](https://github.com/ienam-smarthome/HomeBrainOS/pull/1492) merged to main as `f6084c6d937035450810a6e1ccd577bed94281e8` after all four required CI workflows passed at tested head `e4f6ed530da1bb2755f664f65cc7e10d65d666bd` (Hubitat MCP AI tests, repository validation, release assurance including full Python suite and add-on smoke, and Answer Quality scorecard integrity). 12 isolated tests also passed locally. These are code-level tests, not evidence of model first-answer improvement. This operator is **not yet wired** to actual MCP event history, plan output or final-answer synthesis. Phase 2 still needs validated device/attribute/source/page provenance, reliable adapter normalization, a general question-to-proof contract, bounded continuation for native history when available, source-qualified arithmetic, and held-out evaluations. First priority remains the source-real v0.18.443 read-only humidity/novel-history acceptance with full Technical JSON. Original reported Claude sample values are unverified as ground truth.

---

## 2026-11-06 — Autonomous evidence-first architecture: Phase 1 merged v0.18.443 (live evidence pending)

**CI and merge verified:** [PR #1490](https://github.com/ienam-smarthome/HomeBrainOS/pull/1490), exact CI-tested head `08fecd2faa5b5747ca6a1876bc47062631208c0a`, four required workflow successes (Hubitat MCP AI tests, repository validation, release assurance including full Python suite/add-on smoke/metadata, Answer Quality scorecard integrity); squash merged to `main` as `33a4c7ef74c2a6283517601171067c9a6d585195`. Verified main package `0.18.443`, default `general_task_engine_enabled=true`, configured emergency outer tool rounds `18`, operational deadline `180s`, sensitive confirmations `true`. Direct constructors retain legacy 9-round default to protect write/confirmation regression tests; package factory/config supplies 18. **These are code-level CI results; installed Home Assistant option values, deployed build SHA, real model tool selection and answer-quality gain are not yet verified.** Existing installations may preserve saved `general_task_engine_enabled=false`/`unified_mcp_max_tool_rounds=9`; inspect options after update before claiming planner activation.

**User direction:** Stop relying on repeated user-provided failure examples and per-room/phrase rules. HomeBrain should autonomously understand unfamiliar questions, decide necessary evidence, select/discover MCP tools, execute safe reads, validate coverage and calculate/answer naturally on the first attempt where sources permit. **Remove arbitrary read-only exploration ceilings**, not permission, cancellation, cost or runaway-resource safeguards. Permanent staged roadmap: [HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md](HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md). The revised architecture supersedes continuing one production patch per failed question, while preserving the fixed Answer Quality charter and frozen evaluation cases.

**Triggering source-real failure:** A read-only question asking when bathroom humidity was last above 70% and how long until the first subsequent recorded value below 60% received a v0.18.441 HomeBrain response after 7 model rounds and 6 calls: initial fuzzy lookup missed, the resolver identified Bathroom Meter ID 7851, whole-device snapshots and room/humidity filtering ran, **no device-event-history read** was attempted, then `device_history` was correctly reported missing. Claude's visible answer states last >70% observed 14:25 at 74%, first <60% observed 18:26 at 59% (4h 1m between recorded samples) and earlier peak 86% at 13:05; the raw Claude MCP receipts were not provided, so source-row correctness is not independently verified. The failure was model tool-selection and host evidence-completion, not lack of an installed Hubitat event-history capability. This is one case, not a population-wide accuracy score.

**Source code diagnosis:** General task planning was off by default; source-class completeness could warn after one model retry but did not ensure a feasible missing source was read. Independently, `reasoning_policy.py` enforced 8/12/18 model-selected read-call and 3/5/7 read-round soft limits; the orchestrator cut certain read-only investigations to 3 or 6 rounds and capped source checkpoint offers at 3; fuzzy discovery's top-two gateway heuristic also inadvertently applied to explicit exact operation matches. Outer wall-time/deadline and write confirmation are distinct safety protections.

**Phase 1 implementation:** v0.18.443 enables model semantic planning for non-conversational read-only tasks by default; the model can propose a typed, target-scoped `homebrain_device_history` read with explicit attribute and source window. The host checks installed tool and effect, validates argument schema, resolves target identity via the existing MCP service and passes the **executed** read result back to the model. This is generic across recorded device attributes, not bathroom-specific. Autonomous read-only mode retires the arbitrary soft read/round/checkpoint ceilings; source progression still requires new successful read scopes, and exact tool discovery may keep more than two verified matching gateways. The tool model-context budget is configurable; the operational deadline (180s), per-read timeout (30s), emergency outer round ceiling (18), mutation permissions and confirmations remain. No paid-model escalation, hub change or unattended background execution was introduced.

**Evaluation and rollback:** Phase 1 code/tests/CI are complete, but no source-real v0.18.443 (or successor) deployed first-answer improvement, verified duration calculation, or held-out model A/B exists yet. Request one normal Ask humidity query with full Technical JSON and a novel temperature/power/energy threshold question. Judge whether the required `homebrain_device_history` read actually ran, correctly resolved the source, established the samples and answered without claiming exact physical threshold time. Compare against same-case baseline and inspect unrelated status/control latency, tool costs, privacy and write safety. Disable `general_task_engine_enabled` or revert v0.18.443 if regressions; do not hide limitations by removing the operational deadline.

---

## 2026-11-06 — Q1 source-scoped historical log reporting (v0.18.442 candidate)

**New live read-only result:** The user submitted a v0.18.441 normal Ask response and full Technical JSON showing the intended history-loss causal claim was withheld. The independently typed Hubitat critical-memory/reboot warning at 16:41:40, sunrise/sunset update at 16:44:20 and startup at 16:52:15 UTC were retained. The MCP made two **different** successful native log reads: a bounded mode-omitted `hub_get_logs` query (upstream defaults to `past`), zero matches from 10,639 pre-filter source rows, and an explicit `past` unbounded limit-10 sample with 10 timestamped device-identified messages (10,640 raw source rows). **No source confirms the original memory consumer, missing-log purge mechanism or oldest retained timestamp.** The 40.3-second observation is not a complex-investigation quality threshold.

**General evidence-presentation defect:** Although the two MCP calls were different, v0.18.441's guarded answer reused the bounded zero-match page under both query headings. Its next check also requested another recent sample even though one had just been checked. The fix is not additional case-specific model censorship, but preserving **mode-scoped historical-page attribution** and source-aware next checks. Candidate v0.18.442 keeps legacy aggregate source metadata while adding `mode_page_observations` to ordinary Ask and dedicated incident Technical JSON; recent explicit-past and bounded omitted-mode/default-past counts remain distinct. If a recent sample exists, next checks focus on verifying actual oldest/latest native source time and timezone, not repeating that small read.

**Acceptance and measurement:** Add synthetic tests for the exact live call pair, separately scoped positive/empty pages and failed/unverified receipts. Do not introduce extra MCP/model calls, writes, timeout changes, historical absence conclusions or a fixed latency target. All required CI must pass before merge. Whether this improves live first-answer usefulness remains **NOT MEASURED**. Never interpret raw pre-filter row totals as the requested historic-window count or as proof of complete retention.

---

## 2026-11-06 — General historical-loss claim coverage, v0.18.441 merged (live retest pending)

**Merged code and CI:** [PR #1487](https://github.com/ienam-smarthome/HomeBrainOS/pull/1487), exact tested head `38f1b31aea10766e71d75add7d3221046661baf3`, four workflows green (Hubitat MCP AI tests; release assurance including full Python suite, metadata and add-on smoke; repository validation; Answer Quality scorecard integrity). Squash merge `e093bdf32cf60b6ff01b5dc93b3c1960e254da8a`; `main` packaged add-on version now `0.18.441`. **This is code-level verification only**; installed build SHA, live first-answer improvement, earliest retained log timestamp, log-purge mechanism and original memory consumer remain unverified. No Hubitat, HA, router or runtime deadline changes were executed by this PR.

**New live failure (v0.18.440):** The user submitted an ordinary Ask read-only investigation of 5 November 2026 16:30–16:53 GMT, with full technical JSON. A successful unbounded native past read returned 20 timestamped device-identified messages (9,866 pre-filter source rows). The bounded past query returned 0 matched entries (9,867 pre-filter source rows), while independent typed events returned lowMemory at 16:41:40.105, sunriseSunsetUpdated at 16:44:20.990 and systemStart at 16:52:15.774 UTC. The model asserted that a **log purge occurred, likely triggered by the reboot** and the diagnostic buffer **has been cleared**. Those conclusions do not follow from the checked source receipts. It also treated the location event as part of the overall reboot sequence; this is a timestamped observation, not causal evidence. Original memory consumer, actual native log retention horizon and purge mechanism remain unverified.

**Root cause in guard logic:** The v0.18.440 publication guard matched explicit conjunctions such as logs being purged *due to reboot*, but not unsupported nominal loss claims (a log purge occurred) or direct loss-state claims without a nearby cause connector (buffer has been cleared). As a result, the unresolved historical source assessment did not trigger the safe answer despite unverified discriminating checks. The original model text is available as source-real regression evidence; no new Hubitat reads are authorised.

**Candidate v0.18.441 general correction:** In the same unresolved investigative publication boundary, detect unqualified historical source-loss assertions across active/passive/nominal forms, independently of their alleged cause. Preserve explicitly uncertain and negative forms. If withheld, keep authenticated chronological typed system/location events, recent and bounded past-log row counts, separate source totals and actionable retention-horizon read-only checks. No incident-specific culprit patches, private-log exposure, device changes, new MCP/model rounds or fixed investigation-duration requirement. Regression suite includes the exact v0.18.440 wording and counterexamples.

**Evaluation:** Expected improvement is safe, evidence-qualified first answers to historical coverage questions; **NOT yet measured live**. Green CI is a required code-level gate only. Before declaring resolved, deploy tested build, rerun the original question and inspect `ai_claim_validation`, `causal_read_source_coverage`, returned typed events and unsupported retention language in complete Technical JSON. Roll back on privacy/safety or unrelated control regressions.

---

## 2026-11-06 — Source-grounded historical retention causes (green merged v0.18.440; live retest pending)

**CI and merged code:** [PR #1485](https://github.com/ienam-smarthome/HomeBrainOS/pull/1485) tested head `cf957129a2bce81f45741d0bc4b632f090218f4c`; all required workflows green (Hubitat MCP AI tests, scorecard integrity, repository validation, release assurance including full Python tests/metadata/add-on smoke). Squash merged to main as `98d188124b12aaaba5b2dc76b3d7f21a2f550738`. Main's packaged version is `0.18.440`. **This is code-level verification only**: installed build SHA, model answer-quality gains, purge mechanism, actual oldest retained native-log timestamp and original memory-consuming process are not verified. Next safe live check: rerun the same historical coverage question read-only with the complete Technical JSON and compare first-answer source qualification, not speed or a presumed explanation.

**Source-real 0.18.439 live input:** Ordinary Ask (Gemma4:31b Free, ~36.9 s displayed, seven model rounds and four executed read calls). Read-only `hub_get_logs(mode=past,limit=20)` returned 20 timestamped log messages, one with app source ID and 19 with device source IDs. Pre-filter source rows were 9,082; this recent sample did **not** establish the oldest retained timestamp. The date-bounded 05 Nov 16:30–16:53Z past request returned zero matching rows from 9,085 reported raw source rows. Typed system events independently returned `lowMemory` 16:41:40.105, `sunriseSunsetUpdated` 16:44:20.990 and `systemStart` 16:52:15.774 UTC. The model asserted without discriminating proof that restart/firmware *purged* historical logs, rather than stating that retention cause is unknown. It treated the sunrise/sunset update as part of the reboot sequence and displayed a literal backslash-n in the evidence-coverage tail. The exact original process responsible for low memory remains unverified.

**General Answer Quality correction:** Candidate PR v0.18.440 extends the source-qualified causal publication gate to confident assertions about *why historical log messages are absent* when discriminating checks remain unverified. Its grounded report preserves recent-page app/device counts, empty bounded-page source totals, chronological typed events (including the sunrise/sunset update without causal interpretation), and safer retention-horizon next checks. Weakly phrased hypotheses and completed verified cases are not rewritten merely for mentioning a reboot. Existing source-coverage warning escapes are formatted properly. No new Hubitat/MCP/model reads, writes, polling, cloud escalations, changes to runtime deadline or arbitrary complex-investigation time target.

**Measurement/gates:** Hypothesis is improved factual accuracy and first-answer usefulness for historical retention questions, not proof of retained 5 Nov logs. Full frozen tests/CI must pass; live 0.18.440 grade, original memory consumer, oldest native-log date, and any true purge mechanism are **NOT MEASURED / NOT VERIFIED**. Independently verify actual source timestamps before a definitive retention explanation. Roll back on privacy/safety regression, unsupported cause promotion, malformed event chronology, or unrelated routing changes.

---

## 2026-11-06 — Q1 historical past-log zero-match semantics (v0.18.439 merged; live retest pending)

**CI and merge:** [PR #1483](https://github.com/ienam-smarthome/HomeBrainOS/pull/1483) was tested on exact head `7cac4c6832b26442866484f6dfc0bde5616193cd` and squash merged as `4716c7e63580a57456dc6107cdcc920a6f893e4e`. All four workflows passed (scorecard integrity, Hubitat MCP AI tests, repository validation and release assurance including smoke, metadata and full Python suite). Main package reports version `0.18.439`. These are **code-level test results only**, not evidence that the installed HomeBrain version updated or that retained November 5 log messages were recovered. Next safe evaluation is one read-only normal Ask comparison of the same incident with full Technical JSON, then human review of usefulness versus v0.18.438.

**Source-real observation:** The user's self-reported installed v0.18.438 ordinary Ask for 5 Nov 16:52 restarted from the Hubitat critical-memory warning (16:41:40 UTC) then systemStart (16:52:15 UTC). Read-only native `past` query of 5 Nov 16:30–16:53Z succeeded with `sourceRowsReported=16893` (unfiltered Hubitat source row count), `matchedRowsReported=0`, `returnedRowsInspected=0`, no continuation page and no truncation. The raw source total is **not** a count of rows in the requested incident window. The exact oldest/newest retained log times, hub timezone basis and original memory consumer remain **UNVERIFIED**. Two time-filter/mode calls were blocked before MCP execution. One run: 57.2 s displayed, 8 model rounds, 6 executed tool calls; descriptive, with no 45-second target.

**General answer-quality gap:** v0.18.438's final source-check wording recommended examining returned messages even though the successful filtered `past` page contained none; it also omitted the pre-filter raw row total from the user-facing answer. Candidate v0.18.439 presents bounded numeric per-page observations and distinguishes an empty filtered page from missing/summary-only response and from full historical absence. It prioritises verifying retention horizon and source-time scope using separate read-only bounded source checks, not speculating about an app leak. Ordinary Ask and dedicated incident reports are both updated; no added read, write, polling or cloud escalation. Causal guard still withholds unsupported original-memory-consumer assertions.

**Measurement and acceptance:** Expected improvement is truthful evidence-specific next steps on empty pages, not deeper historical evidence or faster execution. Synthetic empty/positive/failed page regressions and all required CI must pass before merge; future live first-answer usefulness and raw log retention remain NOT MEASURED. Preserve Q1 source-contract work, standing permanent benchmark, no fixed complex-investigation latency cutoff and read-only safety boundaries.

---

## 2026-11-06 — Q1 typed native historical past-log coverage (green merged v0.18.438)

**Merged and CI evidence:** [PR #1481](https://github.com/ienam-smarthome/HomeBrainOS/pull/1481), exact tested head `778671e5034533389325e34bd9f2a08d3e1292fc`, squash merge `fd5a2282010ed05127eccdbc077adf0a4179a4e6`. All required GitHub workflows passed after the architecture module-map entry was added (Hubitat MCP AI tests, release assurance including full Python suite, scorecard integrity and repository validation). Main's package version is 0.18.438. **No live deployment or native 5 Nov message recovery was verified by these tests.**

**Live failure source:** The latest user-supplied 0.18.436 ordinary Ask (Gemma4:31b free) displayed ~35.0s, 7 model rounds and 5 MCP calls; Hubitat’s 05 Nov 16:41:40 critical-memory/reboot warning followed by 16:52:15 startup was verified from typed system events. The later memory-consuming app/process remains **unverified**. A past-log request succeeded but its public receipt had only keys/mode/count, not independently inspected messages; the published app-message evidence remained zero, meaning **unverified actual row coverage**, not proven absence. A synthesis repair failed; exact reason is unavailable in the supplied public receipt. This is one real observation, not a statistically controlled A/B or a source-complete Claude comparison.

**General fix hypothesis:** Source-qualified read-only native past-log receipts should distinguish actual returned timestamped app/device message rows from a successful summary-only request. Candidate 0.18.438 projects bounded numeric row counts, independently confirmed native app/dev numeric source markers and pagination/truncation without publishing raw private message text, names or cursors. Since native past logs may use hub-local clock text, no unverified UTC normalization or historical period completeness is inferred. Ordinary Ask causal guard, explicit incident AI output and final synthesis evidence ledger share this proof, with a source-scoped page key so independent page reads are not collapsed.

**Expected effects / measurement:** Improve precision of technical historical-log coverage and reduce unsupported model statements about source absence. **Not yet measured:** source-real app messages recovered; original memory consumer; comparative first-answer usefulness, causal calibration, latency, failed synthesis repair rate or Claude gap. No additional reads, device changes, app settings changes, cloud spending or timeout adjustments. The 45-second complex-investigation quality cutoff remains retired; median/p95 stay observational. V0.18.437 chart/grid release is independent and preserved.

**Acceptance / risk / rollback:** Source-shape and privacy tests, existing frozen synthetic suites and all repository CI required checks green before merging. The only positive row counts require actual successful read-only native returned entries with parseable source-local time and typed source markers; response summaries and app runtime stats cannot stand in for messages. Revert on raw log leakage, model cause overclaims, schema mismatch or new unrelated regressions. After merge and user deployment, compare one read-only test with full Technical JSON; evaluate source-row proof without assuming that records from 5 November still exist.

---

## 2026-11-06 — Investigation latency acceptance policy revised after v0.18.436 live review

**GREEN MERGED:** [PR #1478](https://github.com/ienam-smarthome/HomeBrainOS/pull/1478), exact CI-tested head `20b251eb7837e719c5f1977fba959a8aca69348c`, squash merge `4f87b3a5d88b38a993d3208a95a6b240bdaea6a1`. All required workflows completed successfully (scorecard integrity, repository validation and release assurance, including full Python tests, metadata and add-on smoke). This policy/scorecard edit does **not** update or deploy the HomeBrainOS add-on. No human-graded improvement to investigation correctness or latency has been measured.

**User-directed policy:** Retire the permanent **45-second preferred complex-investigation target** as a quality acceptance threshold. In-depth Hubitat/HA historical investigations prioritise a useful, complete, source-grounded answer, explicit unknowns and **zero unsupported definitive causal claims**. Slow alone is not a quality failure, and fast alone is not a successful investigation. The **15-second common status/control target remains**. Wall-time, provider/MCP timing, tool/model rounds, redundant calls, median and p95 remain observable for *comparable verified live cohorts*, not pass/fail criteria for complex investigations. These are quality-programme and offline scorecard changes, **not** changes to installed add-on version or runtime code. Existing technical deadlines, timeout handling, cancellation, budgets and device/write protections remain unchanged and may be separately reviewed with source-based evidence. No Claude-vs-HomeBrain time comparison has been independently measured; no Claude timing assumption is used.

**Latest real read-only sample:** User-supplied ordinary Ask technical JSON reports v0.18.436, Gemma4:31b Free, **34,967 ms displayed** (≈35.0 s), agent 33,532 ms, provider 26,662 ms, MCP 6,653 ms, **7 model rounds / 5 tool calls** and one invalid time-filter/mode request blocked before MCP. Typed Hubitat events verified **05 Nov 16:41:40 critical-memory/reboot warning** followed by **16:52:15 startup**, in correct chronological order. A time-scoped `past` log request and `hubEvents` request succeeded **1/1 each**, but receipts provide summary fields rather than verified historical app-message rows; `verified_bounded_app_message_rows=0` is **no proven rows reviewed**, not proof of no matching underlying events. The response still withheld the model's unsupported causal attribution and reported the original memory consumer unverified. One synthesis repair failed. Source data also contained post-start severe CPU-load events, but those do not independently identify the pre-reboot memory consumer.

**Comparison to previous single v0.18.435 observation:** 45.9 s displayed / 8 model rounds / 8 tool calls. The newer run took less time and issued fewer calls, but **not** a controlled or repeated same-source A/B and not a human-graded complete answer. Do not claim a verified speed distribution, model superiority, or a completed causal investigation. Installed version is self-reported; deployed source SHA and actual first-attempt model delivery remain unverified. The still-unresolved priority is meaningful historical `past` message coverage and model answer usefulness, not shaving seconds to satisfy a fixed target.

**Repository source of truth:** [Answer Quality Charter](ANSWER-QUALITY-CHARTER.md), [agent instructions](../AGENTS.md), and the offline `scripts/answer_quality_scorecard.py`. The scorecard retains live investigation median/p95 but sets its `charter_target_seconds` to null; this is **no fixed target**, not missing telemetry or a passed gate. Existing historical review entries mentioning the old 45-second goal remain archival facts and are superseded by this policy. The permanent benchmark-first charter, frozen-case comparison discipline, safety and privacy rules remain in force.

---

## 2026-11-06 — Q1 native log-mode contract correction after v0.18.435 live replay (subsequently merged as PR #1477)

**Observed read-only live sample:** Ordinary Ask `route=unified-mcp-agent` on self-reported installed HomeBrainOS 0.18.435 and Free gemma4:31b, one 05 Nov low-memory restart investigation, 45.9 s displayed / 43.5 s agent, 8 model rounds, 8 tool calls, 38.1 s provider, 5.2 s MCP. The final answer safely retained bounded typed Hub Events, including 16:41:40 explicit critical-low-memory/reboot warning and 16:52:15 systemStart, while withholding the unsupported model root cause. Source verification is **reporter evidence only**: no process consumed memory was identified and neither first model input nor deployed build SHA was independently verified. Two post-start severeLoad events were visible in receipt but not rendered; the reported load values alone do not establish a pre-restart cause.

**Confirmed general MCP contract gap:** The existing successful `past` log read is the historical-message source. Three additional unsuccessful reads used `apps`, `devices`, `hubActions` with historical since/until: upstream MCP log mode schema explicitly forbids dates on those modes, and apps/devices are **runtime stats**, not historical logs. Their actual returned error strings were not in the posted receipt summaries, so the incompatibility is a contract match, not a verified exact error-body quote. Earlier v0.18.435 'App-mode log' labelling was semantically misleading.

**Candidate v0.18.436 general correction:** Model-selected invalid mode/time combinations are blocked *before MCP execution* with read-only schema guidance; date normalization only applies to temporal modes; typed events are displayed chronologically and distinguish a verified **reported** reboot context from the unknown source of memory pressure. Separate runtime-stat and past app-log coverage fields keep the distinct source classes intact. No new live Hubitat/HA polling, writes, background tasks or automatic paid escalation. Test exact PR head in CI before merge.

**Measurement / next action:** Existing v0.18.435 result is an **individual live partial usefulness observation**, not a matched A/B experiment or human-graded 53-case benchmark. Factual cross-case grounding, first-answer usefulness improvement, latency percentile changes, original memory consumer and specific historical message coverage remain **NOT MEASURED**. After CI and deployment, rerun one ordinary Ask read-only case and the dedicated dashboard AI investigation once; capture both full technical JSON and if available deployed SHA. Continue standing model-neutral Q1/Q2 milestones rather than coding an incident-specific culprit rule.

---

## 2026-11-06 — Q1 shared guarded-answer and log-contract evidence review (green merged PR #1475)

**Live evidence:** Two original v0.18.434 Hubitat restart investigations were submitted to ordinary `/api/ask` (`route=unified-mcp-agent`, `request_provenance.source=api_ask_request`). Neither tests the explicit `/api/hub-diagnostics/investigate` incident handler. The 16:52 low-memory report was replaced with a generic unresolved-claim rejection; the 22:33 firmware/startup report retained a useful but incomplete model timeline. The actual tool receipts show successful `hubEvents` and `past` queries in both, plus one successful unbounded `apps` query; their summaries do **not** certify historical app-message content or completeness. Version 0.18.434 is self-reported; deployed Git SHA and model first-attempt delivery remain explicitly unverified.

**Green merged, code-level correction:** [PR #1475](https://github.com/ienam-smarthome/HomeBrainOS/pull/1475) v0.18.435 adds source-qualified, read-only log-mode query coverage to both normal Ask causal guard and explicit incident response. It preserves authenticated bounded typed Hub Events facts only when real typed rows appear in receipts, and never promotes summary-only field names or an unbounded apps snapshot into proof of historical message review. Raw log messages and secrets are excluded from newly published metadata. No extra reads, writes, automatic polling, provider calls or paid escalation.

**CI and merge:** Exact tested PR head `9b5abf27cf39d8c34992290b6c8c21e074555a93`; all **6 required checks successful** (scorecard integrity, add-on smoke, metadata, full Python tests, repository validation, Hubitat MCP AI tests). Squash merged to `main` as `74baa4158147fe6c6c509d790a7e561330446fca`. Main's packaged add-on version is `0.18.435`. This is a code-only CI pass, **not** proof that any installed build updated or any root cause has been found.

**Hypothesis:** Keep independently verifiable evidence useful despite unsupported AI causality, without weakening the zero-unsupported-definitive-cause guard. **Baseline:** submitted 2 cases, no independent paired same-source v0.18.435 live retest. **Acceptance:** cross-path synthetic tests and all required CI green, then one read-only paired normal Ask/explicit incident examination with complete evidence/Technical JSON and build SHA where available. **First-answer quality, actual app memory consumer, root cause and model-comparison improvement: NOT MEASURED.** A green CI result is not a user-graded quality score.

**Rollback:** Revert v0.18.435 if the guard promotes unverified source text, leaks messages, changes write permissions, or fails unrelated Answer Quality tests. Continue the standing frozen-case Q2 benchmark; do not manufacture missing old logs, grades or a source-trigger inference.

---


## 2026-11-06 — Q2 real no-cloud evidence-first prompt A/B: 16 requests, no demonstrated semantic gain

**Code GREEN MERGED:** [PR #1467](https://github.com/ienam-smarthome/HomeBrainOS/pull/1467), exact tested head `d7334993d5cbbde5538ffe7fc7020f724504360d`, merged `a6c87abdfefedc6e357a77d5bbbb96186c85ca16`; **8/8 CI checks passed**, including actual tiny-local-model inference. [Source-bounded results](ANSWER-QUALITY-Q2-EVIDENCE-FIRST-AB-RESULTS-20261106.md), [actual no-cloud trial](https://github.com/ienam-smarthome/HomeBrainOS/actions/runs/42234238612).

**Measured transport only:** Four unchanged frozen source cases × two tiny local models (`qwen2.5:0.5b` and `llama3.2:1b`) × old vs optional evidence-first prompt. **16/16 requests returned nonempty text** without automatic retry; no raw model response published. Candidate minus baseline per-case request-time median **+346 ms** over eight matched model/source pairs, candidate faster **3/8**. Qwen: faster **3/4**, median **−61 ms**; Llama: faster **0/4**, median **+1,966 ms**. In two Qwen comparisons, both variant answer digests were identical. No provider finish reason independently attested, no repeated inference distribution. No model outputs or semantic reviewer grades were available; **grounding, causal correctness, first-answer usefulness and Claude/Gemma parity still NOT MEASURED**.

**Decision:** **Do not promote the evidence-first prompt into production**; additional tokens slowed the Llama calibration model and no source-reviewed quality noninferiority has been established. The optional offline prompt experiment remains reproducible for future privacy-safe source review, but does not change HomeBrain runtime/model routing, installed version, Hubitat/HA, devices or any Cloud usage. Avoid further ungraded prompt iterations: next meaningful Q2 result requires privately retained full first answers and independently completed source review of the same model and same frozen packet. If unavailable, preserve `not_measured` rather than invent accuracy, or redirect development to general source-contract corrections substantiated across multiple live read-only cases.

---



## 2026-11-06 — Q2 general evidence-first prompt A/B against identical source packets (candidate)

**Source base:** `b6623ed9c1360ae14899ed3b0d239fe27e3e6830` (#1465). Production add-on stays at v0.18.427; no fresh installed-build attestation, no model-route change. Two of eight original archived Q2 answer texts have been independently rehashed; the other originals remain unavailable to this evaluation. Formal first-attempt semantic-quality reviews still have **0 independently authenticated grades**.

**Next permanent Q2 milestone:** Keep `render_comparison_prompt` frozen and introduce one optional **model-neutral evidence-first reasoning** candidate for comparative offline evaluation. The candidate encourages source-role distinctions, separates observation, intent, command, configuration and physical confirmation, refuses to infer causes from time order or absence from bounded data, and lets models write **natural** answers. Candidate tests prove the same question and full evidence packet for all **40** curated cases, excluding private reviewer rubrics.

**Actual model experiment:** The isolated, public GitHub workflow will use two very small local models on **four fixed cases** to compare both prompt variants under equal sampling settings, with request order alternated. **16 total requests / 8 paired model-case comparisons** if all execute successfully. Only source/prompt/answer hashes and timing leave CI; raw model answers, keys, private logs and household data do not. **No automatic semantic scoring**, no Claude/Gemma inference, Cloud spending, MCP calls or live Hubitat/HA mutation. Source-based accuracy improvement and natural-answer noninferiority remain **NOT MEASURED** until actual answer texts are privately and independently reviewed.

**Acceptance:** Focused tests + repo CI + actual isolated no-cloud model job required on exact PR head before merge. Passing CI proves safety, fixed source and transport, **not answer correctness**. Roll back optional prompt/runner if candidate causes unreliable completions, disclosure or regressions. See [Q2 experiment notes](ANSWER-QUALITY-Q2-EVIDENCE-FIRST-AB-20261106.md). Next practical gate is reviewed same-model/same-source output from this experiment, not hardcoded repairs to the four incident phrases.

---



## 2026-11-06 — Q2 original-answer byte gate, per-session independent review candidate

**Current branch base:** `b6963fd80cbaedd766644b6065214f19ea673272` after green-merged PR #1462; maintained add-on remains 0.18.427. The existing frozen 40 offline/13 legacy cases and original four Qwen-vs-Llama session metadata are unchanged. No production answer-quality gain has been measured.

**New evidence reused:** Two **verbatim earlier user-provided Llama first-answer texts** (MQTT broker/endpoint and OFF-command attribution) were retrieved from prior conversation context and independently rehashed to their original archive SHA-256 values. That verifies **2/8 original answer plaintext digests**, not provider delivery, physical truth, semantic correctness, or an independent reviewer. No model rerun, cloud call or live home-system tool was used. The other six originals are not verified by this newly created gate and must not be reconstructed from summaries.

**General offline engineering:** Add `scripts/answer_quality_q2_original_reviews.py` and private-file adversarial tests. The tool validates actual locally supplied first-answer bytes against archived original digests before accepting *optional* user-supplied answer-SHA-bound independent source reviews. Each of the four historical sessions is scored, if at all, **separately** through the existing paired-review code; four distinct checkout SHAs cannot become one misleading same-build accuracy score. Absent grade manifest = `not_measured`. File paths, original raw response texts and answer digests do not enter published output. It introduces no automatic human grades, model calls, device writes, runtime changes, version bump or cloud cost. [Read-only gate notes](ANSWER-QUALITY-Q2-ORIGINAL-REVIEW-GATE-20261106.md).

**Acceptance complete — GREEN MERGED:** [PR #1464](https://github.com/ienam-smarthome/HomeBrainOS/pull/1464), exact-head `68ea33b5cc17e75968428a13a706c28724f4eb7a`, merge `b60d3f5af7e7425e0660844b8d82466a90740a88`. **All 6 required checks successful** (full Python suite, offline scorecard, add-on smoke, metadata and two validation jobs). These tests check original-byte, privacy and review-identity handling, **not** factual answer quality. The official first-attempt Q4 accuracy denominator remains **0 independently authenticated human grades**, and no Claude-parity or production latency result follows. Roll back if any original-byte/privacy gate is bypassed or cross-build grades are pooled.

**Next:** Inspect truly accessible private original texts and independently reviewed source claims; count only exact digest-bound graded cases. If the remaining originals are not available, retain `not_measured`, then test a generalised evidence-first reasoning candidate on unchanged cross-domain packets without installing a live rule or adding another incident-specific output guard.

---


## 2026-11-06 — Q2 four recorded local pairs reconciled to frozen evidence inputs (offline audit candidate)

**Current source baseline:** `main` was `3e8b7cdde3e932291f95d375acec7b190e6d671a` after PR #1460, and installed HomeBrainOS 0.18.427 had a source-backed 7.069-second two-device live status sample. That single live read did not certify first-attempt delivery or a cross-version accuracy improvement.

**Next permanent milestone executed:** Four previously provided local-only Qwen3.5:4b versus Llama3.2:3b first-answer pairs (MQTT, OFF-command provenance, heating and Rule Machine identity) have existing private/raw answer digest records and non-blinded qualitative source inspections. Their original model-only timings, answer SHA-256 and frozen packet hashes are transcribed as *metadata only* to `tests/fixtures/answer_quality_q2_recorded_pairs_v1.json`. `scripts/answer_quality_q2_recorded_pairs.py` now checks each recorded pair against the current immutable frozen packet and source-manifest schema, then reports original observed request timing and per-case checkout boundaries. These four sessions had **four different checkout SHAs**, so do not combine them into a same-build model quality score; within each pair the checkout matches.

**Evidence and claim boundary:** The archived qualitative reviews already document Llama faster in all four recorded model-only calls but missing vital evidence/causal mistakes; Qwen generally covers more but overclaims mechanism or causal delivery in some cases. This script **does not** read private original answer bytes, assign rubric grades, authenticate provider ingestion, prove exact model identity or calculate factual accuracy. **0 independently authenticated human first-answer grade rows; official scorecard NOT MEASURED.** No repeat user request is justified just to obtain historical metadata. See [Q2 historical provenance audit](ANSWER-QUALITY-Q2-HISTORICAL-PROVENANCE-20261106.md).

**Acceptance and rollback:** [PR #1461](https://github.com/ienam-smarthome/HomeBrainOS/pull/1461) **GREEN MERGED** as `c39b9b87f7e1a7a58162885ea2f92399db7e1aa7` after **5/5 exact-head CI checks passed** (full Python test suite, offline scorecard, add-on smoke, metadata validation and workflow validation). The four previously recorded source hashes were accepted by the new strict regression gate. This is input/metadata verification, **not** verified improvement in model answer accuracy. Regression tests must reject changed packet hash, original metadata rewrite, duplicated first attempt, checkout mismatch, same-model comparisons and raw private answer text. No production add-on version bump, Hubitat/HA interaction, writer or Cloud model spend. Roll back if recorded metadata fails source-fingerprint validation, or the audit claims an unsupported graded improvement.

**Next:** CI/merge complete. Attempt a truly SHA-bound source review *only* where original private answer files are accessible and independently inspected, without fabricating reviewer/claim counts. The public archive cannot re-create those bytes or establish model-input delivery. No repeat of the four captured questions is required; if those private originals remain unavailable, treat formal quality as `not_measured` and use the four cross-domain qualitative failure patterns to design an ungraded, evidence-first model reasoning experiment rather than a single-case patch. Continue comparable cross-domain reasoning evaluation, not case-specific publication patches.

---


## 2026-11-06 12:57 UTC — registered two-device live read on installed v0.18.427 (source-bounded review)

**Case:** `multi_device_named`, unchanged registered question. User privately supplied the complete natural answer and Technical JSON plus a screenshot. Independently recomputing the registered question's `collapse-whitespace-v1` SHA-256 matches the response's `request_provenance.normalized_prompt_sha256`. This authenticates the **API-submitted question fingerprint**, not first attempt, actual model input delivery or running source SHA: the response explicitly reports `first_attempt_verified=false`, `model_delivery_verified=false` and `deployed_build_sha_verified=false`. Version `0.18.427` is **self-reported** by the response and is not independently mapped to a deployed commit.

**Source-bounded answer review:** The final answer describes both targeted lights as Hubitat-reported OFF and distinguishes their two different **retained** brightness levels. Each of the **four published device attribute values** (two switches and two levels) agrees with its matching typed `homebrain_resolve_device` targeted Hubitat-state receipt, which has `supports_live_claim=true`; two preliminary targeted `hub_list_devices` receipts alone have `supports_live_claim=false`. No conflicting value was found. The answer attributes no physical outcome, command issuer or historical cause. These reported attributes are **not physical-connectivity proof**, and neither their individual change times nor physical actuation was independently verified.

**Observed one-run efficiency:** user-visible elapsed **7,069 ms** (agent **7,003 ms**, provider **4,021 ms**), **3 model rounds**, **4 tool calls** in counters (2 external Hubitat list lookups and 2 local targeted resolver calls in the evidence), **1 tool discovery**, no write/confirmation and `request_class=live-read`. This single observation is below the charter's 15-second common-status target but cannot establish a latency distribution/p95 or prove improvement over another release. A first model round was recorded as an answer with zero tool calls before subsequent tool reads; the final published answer is grounded by later receipts, but the unattested initial draft must not be graded as the final answer.

**Measurement boundary:** Four source-value matches are a **single observational attribute check**, not a 4/4 cross-case quality rate. The answer is useful and appropriately calibrated on this recorded evidence, but it is **not an authenticated frozen first-attempt review**. No formal scorecard row, factual-accuracy percentage, model-quality gain or cross-version speed win is claimed. Prior local-model four-pair Q2 comparisons remain descriptive until exact private answer/SHA-bound independent source reviews. No further user replay is needed for this case. Continue the permanent benchmark-first roadmap; make no device- or phrase-specific publication patch.

---


## 2026-11-06 — Q2 reviewed-pair integrity and general measurement deltas (offline only)

**Base merged:** [PR #1457](https://github.com/ienam-smarthome/HomeBrainOS/pull/1457) at `59865dfeab4b033ff1da29fba7d35c41ab37e47d`, all **7 exact-head CI checks successful**. v0.18.427 is merged source; it has **not** been independently accepted against a newly installed HomeBrain natural answer. The native one-time schema still lacks installed-runtime proof; no writer is authorised.

**Next permanent Answer Quality milestone:** Compare existing real, SHA-bound first model answers on the **same 40 frozen curated packets**, separately from the 13 live legacy tasks; establish genuinely source-reviewed, first-attempt denominators. The four privately captured local-model pairs remain descriptive qualitative observations, **not** a certified 53-case Q4 benchmark or evidence of Gemma/Claude parity. No raw answers or provider secrets are in the repo.

**This candidate (no runtime version bump):** Harden the existing review scorecard to reject a `causal_calibration=pass` grade when unsupported definitive causes are counted. Add same-packet human-review ordinal changes for all five rubric dimensions, exact-pair unsupported-cause deltas and the median *per-case* offline request-time delta, preserving null outputs for zero reviewed pairs. Unit tests use synthetic reviews and cannot claim real answer gains. No model calls, external tool calls, Hubitat/HA read/writes, add-on routing or natural-language publication changes. Roll back if legitimate reviewed reports are rejected or paired case/provenance identity is degraded. **PR #1458 GREEN MERGED:** [Q2 reviewed-pair integrity](https://github.com/ienam-smarthome/HomeBrainOS/pull/1458), merge SHA `2409a8155f6256ceef63c849bccdb49f109a3786`; **all 6 exact-head checks green** (full Python suite, add-on smoke, offline scorecard, repository metadata, two validation jobs). Real answer-quality/latency improvement remains **NOT MEASURED**; code change is evaluation-only.

**Next:** After green CI and merge, independently source-review the four existing private local pairs (or obtain one new first-attempt read-only HomeBrain answer/JSON only if live provenance is needed); do not fill reviewer rubrics from synthetic tests, assume a measured baseline, or return to case-specific publication patches.

---


## 2026-11-05 — installed v0.18.426 passed routing/no-write but overstated native contract evidence; v0.18.427 candidate

**Acceptance:** Installed 0.18.426 answered the read-only MCP Rule Server 5.1.6 runbook as `rule_design_review` in 2 model rounds, 3 calls and 19.172s wall. The technical record correctly reported `evidenceComplete=false`, `typed_authoring_contract=checked-unverified`, `questionResolved=false` and Unresolved, with no Hubitat writes. The final text nevertheless labelled unverified typed fields, year# and log action as Verified, conflated numbered `logmsg.#` field placeholders with calendar-year handling, and exposed a guide acknowledgement key and contract-shaped JSON sketch. A generic controller/device evidence disclaimer was irrelevant to contract-only review.

**Candidate repair:** Source-bounded table statuses and schema JSON, guide key redaction, contract-specific evidence qualification, and explicit `readinessForMutation=false` in technical coverage. Preserve actual source-attested findings, ordinary device and named-rule investigations and all no-write permissions. [Release notes](../hubitat-mcp-ai/CHANGELOG-0.18.427.md). CI and installed re-acceptance are separate; do not claim production success before retest.

---

## 2026-11-05 21:42 UTC — installed v0.18.425 answered runbook with parent/name listing; removed fast path in v0.18.426

**Observed live failure:** The exact read-only native dated-trigger contract-review request was intercepted by a deterministic Rule Machine parent/name inventory routine. v0.18.425 returned **Success** in **4.575s**, with **4 nonmutating MCP reads + 1 local typed projection**, 0 model rounds, parent ID **169**, and no exact one-time suffix matches. The requested native trigger types, time/date/year, log-only action and runtime scheduler proof were **not evaluated**. The `investigation_coverage.domain` and `questionResolved=true` were therefore for the wrong task. No rule/device changed or confirmation queued.

**v0.18.426 removal:** Eliminate the special native parent/name inventory module, its orchestrator early return, special completion/Success override, imports, and specialised tests. A replacement regression asserts former inventory-shaped receipts do **not** satisfy the current native authoring-contract review. Normal read-only `hub_list_apps`, `hub_list_rules`, native rule-document read, bounded date discovery, and parent preflight still exist. True installed-rule audits and unrelated device inventory/status paths are preserved. No extra writes, editor forms, authorisation or native scheduling capability.

**After deployment:** Ask the *same* read-only MCP v5.1.6 one-time dated-trigger runbook review. Expect `investigation_coverage.domain=rule_design_review`, `typed_authoring_contract=checked-unverified` without authoritative native field evidence, **Unresolved**, and no parent/name-only success. Compare latency and tool counts with this 4.575s wrong answer and prior 78.710s wrong deep-rule audit; one result is not a quality distribution. Do not create a log-only rule until actual native contract, backup and approvals are established. [Release notes](../hubitat-mcp-ai/CHANGELOG-0.18.426.md).

---

## 2026-11-05 21:23 UTC — installed 0.18.424 native runbook review misrouted; v0.18.425 candidate

**Installed acceptance failure:** The prompt explicitly asked to review the MCP Rule Server v5.1.6 native one-time dated-trigger runbook **READ-ONLY** and compare typed trigger/action schema and date/time formats; it prohibited new rules and unrelated lighting/motion advice. The installed 0.18.424 model/host instead selected `existing_rule_verification` (technical JSON), spent **11 model rounds**, **15 tool calls**, **78.710s wall** (75.399s agent) and retrieved **240,000 characters** of installed app 4151 / code 1501 in five chunks before exceeding the bounded retrieval allowance. Other reads included generic app inventory, guide and recent logs. It returned a generic existing-rule action-tree and controller lockout report, not a field-contract review. `fullImplementationVerified=false`, `evidenceComplete=false`; no modifying Hubitat calls or pending confirmations were recorded. Actual rule-health reads were absent. The v0.18.424 native proposal publication guard did not help because the entire question was routed as an existing-rule audit.

**v0.18.425 scope repair:** Treat positive read-only review of a native **authoring runbook/schema** as `rule_design_review`, even if the advisory model selects `existing_rule_verification`. Do not capture an explicit named installed-rule deep audit; keep it on its original route. Align objective, no-write rule-design handling, evidence requirements (native guide + typed authoring contract, *not* controller/device app config), generic proposal system instructions, and final presentation. Fix negative topic constraints to avoid transforming `do not include unrelated motion/lockout guidance` into an activation of the fixed 23:00–06:00 motion appendix. No new native writer permissions, tool calls, control commands or scheduling tests are introduced. [Release notes](../hubitat-mcp-ai/CHANGELOG-0.18.425.md).

**Acceptance:** Once CI passes and 0.18.425 is installed, repeat a *single* read-only runbook review. Expect `investigation_coverage.domain=rule_design_review` with source-scoped contract requirements and no unrelated app/Groovy reads or lighting/lockout warnings. Actual installed typed trigger and log-action proof remains unverified; report Unresolved when source evidence is missing. Measure wall, provider/tool rounds and calls against 0.18.424's 78.7s/11 rounds/15 calls; do not claim performance gains before that live sample.

---

## 2026-11-05 21:02 UTC — false native Rule Machine readiness in installed v0.18.423; v0.18.424 fix candidate

**Live defect:** A read-only request to review MCP Server v5.1.6 native dated-trigger creation returned a model-authored, executable-looking payload with wrong date/time shapes (`HH:mm`, `MM/dd/yyyy`), fabricated `addTrigger`/`addAction` and `runCommand` syntax, top-level `parent_id`, and declared the proposal READY. The returned source receipts were only two `hub_list_apps(scope=instances)` inventory reads and two `hub_get_tool_guide` sections (4 MCP calls, 3 model rounds, 21.476s wall, 17.504s agent). Technical coverage reported `rule_design_review`, `sourceChecksComplete=false`, `evidenceComplete=false`, device/current-rule sources not checked and native capability source checked-unverified. The model claimed device/app pages and UK hub timezone without matching targeted evidence. An existing shared rule-design guard appended a fixed motion/inactivity/manual-lockout and 23:00–06:00 warning from an unrelated rule-design request. No automation or device was modified or queued.

**Upstream distinction:** MCP Server merged PR #576, issue #575: native `atDate#` type `date` validates `yyyy-MM-dd`; its `atTime#` example is a full native time value, not a bare `HH:mm`. The installed `set_rule_reference` guide still omits a static typed date-trigger template; a successful guide read is not source-attested live authoring proof. The model's contradictory values are not evidence of Hubitat's behaviour.

**v0.18.424 shared guard correction:** Remove unverified schema assertion/readiness sections and runnable native-write JSON from read-only proposals unless a trusted typed combined-schema receipt attests them. Derive evidence qualifications from actual targeted reads, not generic response field names. Choose overnight motion/light warnings only for matching user requests; other design reviews get domain-neutral contract and firing caveats. Keep no-new-tool-calls/no-new-model-rounds/no-writes, and retain original motion-design guard. Add a replay regression with the exact wrong field formats, false READY, fake JSON and injected motion note. This is not authorisation to test or enable native writing.

**Evaluation:** CI and installed acceptance pending. Acceptance should show no false READY, no executable JSON unsupported by typed source, and no unrelated 23:00–06:00 appendix on the same read-only request; benchmark generality and latency against standing Answer Quality roadmap. No native scheduling was attempted.

---

## 2026-11-05 — MCP native dated-trigger guide patch drafted; upstream write access remains unavailable

**Following installed v0.18.423 acceptance:** The native read-only preflight correctly verified parent 169 / type 18, 42 returned child-parent references, MCP Server 5.1.6, and both tool-guide sections. Its `nativeGuideContract.inspectionStatus=checked` did not find `atDate#` typed declarations; `Unresolved` and `readinessForMutation=false` are expected. No further HomeBrainOS runtime patch is justified by this source gap. Continue the standing benchmark-first Answer Quality roadmap.

**Upstream contribution draft:** Prepared [MCP Server 5.1.6 guide patch](upstream-patches/Hubitat-MCP-native-dated-trigger-guide-v5.1.6.patch) plus [submission/validation notes](upstream-patches/README-native-dated-trigger-guide.md). The patch edits the upstream served `set_rule_reference` guide source, corresponding generated `TOOL_GUIDE.md`, and a Spock guide regression. It documents the typed `time#`, `atTime#`, `date#`, `atDate#` pattern from upstream issue #575 / merged PR #576, explicitly separating static guide data from installed page validation and actual one-time runtime firing. Server-served wording contains no issue/PR numbers as required by upstream `AGENTS.md`.

**Access limitation:** GitHub identity `ienam-smarthome` has read but not push access to `kingpanther13/Hubitat-local-MCP-server`, and no owned upstream fork is connected; issue creation previously failed HTTP 403. No upstream change or PR was made. Draft patch location was validated against exact upstream anchors and `git apply --check` on synthetic exact-context fixtures; **full upstream Groovy CI and required dedicated test-hub E2E have not run**. Await fork/maintainer involvement for upstream submission, not repeated live HomeBrain queries.

**Safety unchanged:** No Hubitat read beyond user-supplied prior test data, no native rule/device writes or editor forms, no writer enablement, no create/execute authorization. No HomeBrainOS version bump for this docs-only handoff.

---

## 2026-11-05 — installed v0.18.423 native preflight: evidence-scope correction accepted; upstream date-guide contract still unverified

**Live installed result at 20:11 UTC:** HomeBrainOS reported `version=0.18.423` (the current version includes separate Hub Diagnostics releases 0.18.421–0.18.423). The read-only native Rule Machine preflight correctly returned **Unresolved** with `domain=native_rule_readiness`, `status=partial-evidence`, `evidenceComplete=false`, `questionResolved=false`, `preflightEvidenceComplete=true` and `readinessForMutation=false`. Previously, v0.18.419 incorrectly published guide unavailability and Success for a request explicitly asking for `nativeGuideContract`. The v0.18.420 scope correction has therefore **passed its relevant installed acceptance**.

**Source evidence:** MCP initialize `serverInfo.version=5.1.6`; latest hub-local backup source timestamp `2026-11-05T03:02:31+00:00` (not independently compared to live hub time); both tool guides readable; exact parent app **169** and built-in app type **18** verified from the installed-app/type inventory and **non-rendering** `hub_get_app_config(summary=true)`, with **42 returned** linked child rows (not a complete inventory). The actual MCP reads were backup, 2 guide sections, app instances, app types, and parent summary: **six external reads plus one local typed projection**; no full app-config page render, native writer or model call. Wall `elapsed_ms=5087`, agent `total=1722ms`, aggregate HTTP ~1.6s. Single observed response, not a measured latency distribution.

**Source-scoped date contract remains unverified:** `nativeGuideContract.inspectionStatus=checked`; `createOperationDocumented=true`; `parentIdParameterDocumented=true`. The installed guide does **not** name `atDate#`, `time#`, `atTime#`, `date#`, the `Certain Time (and optional date)` capability or `yyyy-MM-dd` format. It returned six precise missing-declaration codes, not `guide_unavailable_or_oversized`. This means **guide not documented**, not **MCP Server can't support date inputs**. Public upstream #575 was closed by PR #576, which tests native `atDate#` type `date` and `yyyy-MM-dd` support; a test of the upstream implementation is not an independent attestation of the installed hub's saved one-shot trigger or runtime execution.

**No new HomeBrainOS production change justified by this acceptance.** The prior preflight patches have now provided the intended truthful answer and safe non-rendering evidence. Continue permanent Answer Quality benchmark work, avoid repeatable date-specific route patches. Native rule writing remains disabled; explicit user authorization and verified live write contract/backup/target ownership are still necessary before any isolated one-time scheduling test.

**Upstream tracking:** A non-rendering typed date-trigger guide example or schema source would close the remaining documentation gap, ideally augmenting existing `set_rule_reference` rather than introducing an extra tool or page render. The GitHub connector attempted to create a scoped issue in `kingpanther13/Hubitat-local-MCP-server` but was denied with HTTP 403 (integration has no issue-write permission). Proposed text is in [upstream native date guide request](UPSTREAM-NATIVE-DATE-GUIDE-REQUEST.md); upstream issue **not posted**.

---

## 2026-11-05 — installed v0.18.419 parent preflight accepted, guide-contract completion false-positive; v0.18.420 candidate

**Installed 18:05 UTC acceptance:** HomeBrainOS 0.18.419 used six externally sourced, nonmutating MCP requests (backup, two guide sections, app-instance listing, type listing, app summary) plus a local typed receipt. Native Rule Machine parent **169**, built-in type **18** and **42 returned child-parent references** were verified using non-rendering sources; no full app config page, native writer or AI round. Core preflight sources (MCP 5.1.6; 03:02:31 UTC backup; two readable guides) succeeded, UI wall-time **4.185s** and agent phase **1.3s**. This is one live sample, not a latency distribution.

**Remaining semantic failure:** The user's request explicitly asked to report `nativeGuideContract` and its evidence gaps, but the readiness matcher required specific date/creation terminology. Because date inspection was skipped, the response misleadingly published default `guide_unavailable_or_oversized` while both guides were successfully read, and reported `Success` / `evidenceComplete=true` despite not assessing the requested contract. No verified date field, create contract or one-time runtime execution was obtained; `readinessForMutation=false` correctly remained enforced.

**v0.18.420 scope correction:** Recognise requests to report a guide contract/guide gap as source-proof obligations; inspect the already retrieved `set_rule_reference` section for safe typed field metadata without new MCP calls, AI rounds, form renders or writes; disambiguate checked vs unreadable/oversized guide; grade full requested coverage as incomplete if the date declarations are missing, while preserving success for ordinary version/backup/guide availability preflight. Synthetic regressions replay the live report, positive paraphrases, negative instructions and simple preflight. All native Rule Machine writer permission/confirmation and backup constraints unchanged. CI and installed acceptance pending. [Release notes](../hubitat-mcp-ai/CHANGELOG-0.18.420.md).

**Next meaningful milestone:** Verify that 0.18.420 no longer declares misleading guide unavailability or full request success when the actual source lacks dated field declarations. After this limited completion-correction cycle, return to the standing benchmark-first Answer Quality roadmap. Upstream issue #575 / PR #576 support date input types, but no source-verified saved date or runtime one-time execution exists; do not create a probe without explicit authorisation.

---

## 2026-11-05 — v0.18.415 exact native date readback still incomplete; candidate 0.18.416 bounded pagination

**Installed read-only outcome (15:47 UTC):** After fixing the status-route false positive, v0.18.415 returned the correct specialist `unified-mcp-agent` / `native_dated_trigger_discovery` answer in **813ms**, zero model rounds. One native inventory page confirmed 42 visible Rule-5.1 child IDs, including target IDs **2967** and **3985**. The two `hub_set_rule(operation=read,rule_id,args:{sections:[triggers,settings]})` requests completed in **214ms** and **240ms** but both yielded `readVerified=false`; no full typed field readback or enabled date was confirmed. All four evidence receipts (including local projection) were read-only, `readinessForMutation=false`. This **does not prove** that either native rule is corrupt, lacks a date trigger or that Hubitat rejected the read: the old scanner collapsed source errors and document projection failures into a single generic failure and omitted the actual safe failure category.

**Upstream contract verified from public source:** Native `toolGetRuleDocument` performs read without editor form and supports paged **one-section** requests, using `cursor`, `limit`, `page.offset`, `page.total`, `page.revision` and `nextCursor`. The server actively caps JSON response size, so large all-sections documents may fail while small paged reads succeed; this is a testable hypothesis only, not an established cause for 2967/3985.

**Candidate 0.18.416:** For *explicit exact-ID existing native date questions only* and source-verified native inventory IDs, preserve original unpaged read and add a bounded fallback: up to 3 trigger pages and 8 settings pages of 50 rows per ID, with hard total bounds and exact ID/revision/cursor/section checks. Compose the document only on complete read, then apply existing allowlisted typed date-field projector. Expose no raw private settings or MCP exception messages: only safe `unpagedFailureCode`, paged-read status/counts and per-ID `readVerified`. No fallback for unrelated offset scans, mismatched IDs or tool exceptions. A multi-ID retry checks *all* explicitly requested IDs even if one is positive. Writer permission, backup, confirmations, native parent and native dated authoring constraints unchanged. Offline test suite and installed acceptance pending. See `hubitat-mcp-ai/CHANGELOG-0.18.416.md`.

**Next installed test:** Re-run the exact same read-only retry for IDs 2967 and 3985 on v0.18.416, inspect `readDiagnostics` and `pagedSectionsRead` in Technical JSON. If both paging attempts fail, use only validated failure categories to decide whether upstream MCP needs work. Do not assume Rule Machine dated authoring is available.

---

## 2026-11-05 — installed v0.18.414 exact-ID date retry hijacked by global automation-status; candidate v0.18.415

**Live failed acceptance (15:13 UTC):** User ran the prior read-only exact native Rule Machine dated-trigger retry for **IDs 2967 and 3985** (includes exact-ID inventory check, date-field names, non-mutating native read, and explicit prohibition on rule changes). HomeBrainOS v0.18.414 responded in ~**1.0s** with `route=automation-status`: a generic 166-item Hubitat automation inventory (124 apps, 42 Rule Machine entries, 147 active/not-disabled, 18 disabled, one paused—rule 3985 "Internet: Google TV block @1hr"). **No source-attested readback of target date fields was performed.** These inventory counts can be accurate but irrelevant; fast success is not proof that the requested investigation ran.

**Root cause:** `AutomationStatusService.matches_request()` previously decided a global status intent from arbitrary status/list words anywhere in a prompt plus any mention of rules/apps/automations. The safety sentence **"Keep native rule-writing authorisation disabled"** produced a false global status intent for a targeted read-only rule investigation. The /api/ask shortcut was evaluated before dispatch to the dedicated native dated-trigger scanner, so this was a host routing defect, not a model failure or an incorrect underlying rule status.

**Candidate v0.18.415:** Retain the deterministic filterable status UI for **explicit** global inventory/status/count questions; do not remove an otherwise useful fast path. Narrow the matcher to positive broad status phrases, explicitly exclude native existing-dated-trigger investigations and exact rule-ID reads, and add a second precedence guard at the /api/ask shortcut. Regression tests use the exact failed prompt and nearby safety prohibitions, plus genuine "List every automation", "Which rules are paused", "Automation status", and "Recommend useful automations" requests. FastAPI route tests assert no status snapshot on the focused retry and status snapshot preservation on genuine broad requests. No new MCP permissions, native writes, editor form operations or date authoring gates. CI and installed acceptance pending; consult `hubitat-mcp-ai/CHANGELOG-0.18.415.md`.

**Next actual investigation:** Once v0.18.415 is installed, **repeat the same exact-ID read-only prompt** for 2967 and 3985, preserving the "authorisation disabled" clause. Expected `route=unified-mcp-agent`, `domain=native_dated_trigger_discovery`, `scanMode=targeted-rule-ids`, target IDs and per-ID `readVerified`. Do not presume either incomplete read will become valid or date-enabled. The prior four-batch inventory established 42 visible Rule-5.1 candidates attempted, 40 native read projections, two incomplete, and no verified enabled date-specific trigger; that provenance remains unchanged by this misroute.

---

## 2026-11-05 — fourth native date scan closed the 42-candidate inventory; v0.18.414 targeted retries

**Installed v0.18.413 final batch, 14:26 UTC:** UI 4.7s, Technical JSON `elapsed_ms=4684`, no model rounds, 1 inventory + 6 non-mutating `hub_set_rule(operation=read)` + 1 local projection (8 metric calls, 7 external MCP calls). Returned inventory has 42 visible `Rule-5.1` native children and complete page traversal. Offset **36** returned final IDs **4206, 4207, 4239, 4241, 4246, 4259**, all 6 native trigger/settings reads verified. Rule **4246** trigger 3 `time3= A specific time` / `atTime3=23:00` and trigger 5 `time5= A specific time` / `atTime5=06:00`, neither a returned `date#` or `atDate#`. No enabled dated field-set established. `moreCandidatesMayExist=false`, `absenceProven=false`, `readinessForMutation=false`; no Hubitat write.

**Cumulative four batches:** Sorted IDs from the same 42-visible-child inventory attempted exactly once at offsets **0,12,24,36**, **40** complete native read projections and **2** incomplete native reads (rule IDs **2967** and **3985**). These are not negative date-trigger observations, and 42 visible candidates do not attest inaccessible app classes or any runtime one-shot execution. No source-verified enabled dated trigger found in the readable sample.

**Next rational investigation:** Retest the **two exact incomplete IDs**, without looping through 42 again or invoking editor/form routes. Existing v0.18.413 host-owned scanner accepted only numeric offsets, not requested IDs. v0.18.414 candidate adds a narrow explicit-rule-ID retry mode (at most four unique positive IDs) only after fresh visible-native-inventory membership and safe read operation validation. Unknown IDs are skipped, not read. Output separates targeted completeness from inventory absence. Regression includes one matching/mismatching native result and unchanged offset semantics. Native Rule Machine writer minimum MCP >=5.1.6, source/date contract, backup, confirmation, duplicate and write authorization remain unchanged. See `hubitat-mcp-ai/CHANGELOG-0.18.414.md`. CI and installed acceptance pending.

---

## 2026-11-05 — v0.18.413 third native dated-trigger scan accepted (offset 24→36)

**Installed live read at 14:12 UTC:** v0.18.413, 2.022s total, 2.002s agent, zero model rounds, 1 child-app inventory read + 12 native `hub_set_rule(operation=read)` rule reads + 1 locally generated typed summary receipt (14 metric tool calls, **13 external MCP reads**). All 12 native document reads succeeded, none mutated state. One inventory page fully traversed, **42 visible eligible native Rule-5.1 child rules**. This third batch scanned sorted rule IDs **3992, 3996, 4094, 4136, 4157, 4163, 4166, 4177, 4178, 4183, 4190, 4192**; `scanOffset=24`, `scanLimit=12`, `moreCandidatesMayExist=true`, next scan offset **36**.

**Partial stored time-trigger observations:** `4136` trigger 1 `atTime1=22:00` and `4163` trigger 1 `atTime1=09:00`, both with `date1` typed `bool` but no verified bool value and no `atDate1`; `4166` trigger 1 `atTime1=19:00` and `4177` trigger 1 `atTime1=06:00`, neither a returned `date1` nor `atDate1`; `4178` trigger 1 `atTime1=19:30` with `date1` typed `bool` but unverified value and no `atDate1`. Every listed trigger has its native trigger row and source-typed `time1` enum `A specific time`. The readable answer intentionally showed the first four partial observations; the fifth (4178) is retained in Technical JSON `partialTimeOrDateFieldGroups`. **None proves date enabled or a saved one-time date.** `savedDatedFieldReadbackVerified=false`, `absenceProven=false`, `readinessForMutation=false`, `domain=native_dated_trigger_discovery`.

**Cumulative since first 0.18.412/0.18.413 source scan:** batches offset 0, 12, 24 attempted **36/42** of the same visible candidate inventory, **34 independently readable** documents and **two incomplete** native reads (rules **2967**, **3985**). Six as-yet-unattempted candidates remain on unchanged inventory; next scan offset **36** should attempt at most six. Once all candidate IDs have been tried, retry incomplete IDs via explicitly read-only exact-ID native sources before reaching even a scoped absence assessment. This candidate inventory is not proof of complete hub-wide rules or absence of date fields in unreturned data.

**Acceptance:** Correct specialized answer, fast host-owned read-only routing, no unrelated generic action-tree audit and no production regression demonstrated. No new add-on release needed. Do **not** lower the >=5.1.6 native authoring gate, enable a Rule Machine writer or infer runtime execution. User-provided result is not first-model-delivery/deployed-commit attestation.

---

## 2026-11-05 — installed v0.18.413 dated-trigger discovery publication accepted (offset 12→24)

**Installed acceptance at 14:03 UTC:** HomeBrainOS **v0.18.413** correctly displayed the native dated-trigger specialist answer instead of the generic existing-rule/action-tree/inactivity-controller report that had overwritten v0.18.412. UI 4.7s, Technical JSON 4.686s total, 2.270s agent, zero model rounds. One visible Rule-5.1 child inventory page was successfully traversed, showing **42 eligible visible candidates**; 12 native `hub_set_rule(operation=read, sections=[triggers,settings])` calls covered sorted IDs **3090, 3152, 3600, 3602, 3625, 3829, 3931, 3950, 3951, 3985, 3986, 3988**. Of these 11 document reads verified, rule **3985** incomplete/unavailable. One local `typed_native_dated_trigger_discovery` projection yielded 14 total evidence receipts/metric tool calls (one inventory + twelve MCP rule reads + local projection), 13 externally sourced MCP calls, zero write calls. `domain=native_dated_trigger_discovery`, `evidenceComplete=false`, `questionResolved=false`, `savedDatedFieldReadbackVerified=false`, `absenceProven=false`, `readinessForMutation=false`.

**Useful partial stored fields:** rule **3951**, trigger 1 `atTime1=23:30`; same rule trigger 2 `atTime2=06:30`. Rule **3986** trigger 1 `atTime1=04:00`; rule **3988** trigger 1 `atTime1=01:30`. Each has a matching native trigger row plus `time#` typed enum `A specific time` and `date#` typed bool **but without a verified bool value**; none exposes an `atDate#` field. These are ordinary time-trigger observations, not verified date-enabled one-time triggers. The screenshot's wording and typed readback agree.

**Cumulative read-only sampling:** First batch offset 0 attempted 12; second offset 12 attempted 12, so **24 of 42 candidate IDs attempted**, **22 read-verified and 2 incomplete** (rule **2967** and rule **3985**); 18 candidates remain unattempted if subsequent inventory returns the same sorted 42-ID snapshot. No enabled native date field-set was observed in these *samples*. Do **not** infer absent dated rules across the whole hub, or reclassify incomplete reads as negative. Next bounded scan offset **24**, then **36** (at most six remaining on a stable 42-item inventory). Prefer retrying the two incomplete IDs after the remaining candidate batches through exact, independently read-only access, not as writes.

**Acceptance verdict:** v0.18.413 source answer publication **passed installed acceptance**; no immediate new application release is warranted. Continue the bounded investigation only if additional saved date evidence is needed. Native Rule Machine dated authoring remains **unauthorized**, HomeBrain writer >=5.1.6 minimum unchanged, and saved fields do not prove runtime execution or one-time semantics. This is an installed functional observation, not verified first model delivery or deployed SHA identity (`request_provenance` flags remain false).

---

## 2026-11-05 — installed v0.18.412 native date scanner ran, but earlier generic publication overwrote its answer; v0.18.413 candidate

**Actual installed source test (13:30 UTC):** HomeBrainOS **0.18.412**, total 4.671s, zero model rounds, 13 read-only MCP source calls and one local typed projection. Native rule inventory returned **42 visible Rule-5.1 children** with a single complete returned page; scanner read **12** sorted rule IDs (1881, 2075, 2084, 2217, 2305, 2706, 2710, 2817, 2843, 2844, 2967, 3055), 11 read-verified and one rule **2967** unavailable/incomplete. No enabled dated trigger observed, no absence proof, 30 visible candidate IDs uninspected. Scan offset 0, next offset **12**. No Hubitat writes.

**Useful partial stored native evidence:** Rule **2710** has native trigger row 1, `time1` type enum/value "A specific time", `atTime1` type time/value "22:30", `date1` type bool **without a verified boolean value**, and no `atDate1` field. The typed source correctly says `savedDatedFieldSetObserved=false`. This is NOT a verified date-enabled trigger, persisted one-time date or runtime firing.

**Diagnosed output defect:** The `_process_user_request` specialist route already performed the right scanner and recorded `typed_native_dated_trigger_discovery` with `domain=native_dated_trigger_discovery`; however `process_user_request_result` ran `calibrate_existing_rule_verification` under a broad existing-rule objective **before** shared completion set the correct domain. The result's *message* was overwritten with unrelated action-tree, inactivity-OFF, controller, duplicate-rule limitations; the Technical JSON domain remained correct. This proves specialist final coverage alone is insufficient to preserve the message.

**0.18.413 candidate:** Prioritize only a genuinely recorded, read-only `homebrain_native_dated_trigger_discovery` typed receipt before the earlier generic result calibrator; add independent no-overwrite guard inside the generic existing-rule calibrator. Preserve normal calibration if the source receipt is absent. Also publish a small, allowlisted partial time/date observation when relevant fields exist without full enabled-date proof; honest summaries distinguish "native read parsed" from "enabled dated field set verified". Unit/regression tests reproduce the 42/12/11/one-failure live shape and publication order. No extra model/MCP rounds or writer changes. Live v0.18.413 test pending; after installation, rerun same read-only prompt and expect next scan offset 12.

---

## 2026-11-05 — v0.18.411 existing dated-trigger investigation misrouted; candidate 0.18.412

**Observed installed failure:** User tried read-only search for existing Rule Machine `Certain Time (and optional date)` native triggers and stored `time#`, `atTime#`, `date#`, `atDate#` fields. Installed **0.18.411** ran **40.751s**, **10 Gemma cloud rounds**, six nonmutating MCP calls; provider **36.552s**. Instead it selected app **4163** "Block Nest hub from 5.50pm", obtained thin identity+untyped config receipts, plus untyped `hub_list_rules`, health and app logs. It did **not** verify that app 4163 uses a dated trigger or expose persisted date fields. Shared completion selected `existing_rule_verification`, publishing unrelated inactivity-OFF/lockout, duplicate-rule, nested-IF and action-tree limitations. These were not the user's asked-for discriminators. No modifying Hubitat commands were recorded.

**Confirmed upstream read-only capability:** `hub_list_apps(scope=instances,filter=children)` exposes visible child native app IDs, type and parent; `hub_set_rule(operation=read,rule_id,args:{sections:[triggers,settings]})` reads native state and typed settings without native editor/form opening. The upstream v5.1.5 tests document `date#` `bool` and `atDate#` `date`, as well as `time#`/`atTime#` fields; not yet proven from this user's saved native rule state.

**Candidate 0.18.412:** Add strict positive existing-dated-trigger read-only route, bounded at 4 inventory pages and 12 exact-ID native `operation=read` calls per batch. Only safe allowlisted typed date/time fields, no raw private settings, no form open or writer calls. Require exact native rule-ID link, same trigger allocated index, `date#=true`, valid date, time and atTime values to mark a saved dated field-set observed; **do not claim runtime or one-shot execution**. If none found, publish an incomplete bounded scan with next offset rather than claiming absence. New source-typed completion domain `native_dated_trigger_discovery` supersedes unrelated generic rule-health audit. Tests replay original prompt and no-write invariants. Live outcome, actual target rule and latency remain unmeasured. **No change to authoring gate v5.1.6, confirmation, backup or duplicate checks.**

---

## 2026-11-05 — Installed v0.18.411 native dated-rule preflight acceptance PASSED, authoring not yet proven

**Installed response:** HomeBrainOS v0.18.411, same normalized request SHA `2d5f05da71d470ddf20f3a0e0b268af49df5336dd03ee88a7a4188c87dd9c81e`, **4.703s** overall, **1.703s** agent, zero model rounds, four successful read-only external MCP reads and one local typed source projection; no modifying receipts. The native readiness answer survived shared completion, and `investigation_coverage.domain=native_rule_readiness` was preserved (the 0.18.410 app-class-identity overwrite is fixed).

**Observed sources:** `MCP initialize/serverInfo.version=5.1.5` matches independently queried `hub_get_info.mcpServerVersion=5.1.5`, `mcpVersionAgreement=true`. Latest hub-local backup `2026-11-05T03:02:31+00:00`, 24 returned records. Both `set_rule_reference` and `builtin_app_tools_rules` guide sections readable. `preflightEvidenceComplete=true` applies **only to core version/backup/guide availability**, while requested `nativeDatedFieldGuideAttested=false` and `nativeDatedDateReadbackVerified=false` correctly leave `evidenceComplete=false`, `questionResolved=false`, `metrics.outcome=unresolved`, `readinessForMutation=false`. Do **not** reinterpret unresolved as an app-identity regression or as failure of the four completed source checks.

**Upstream independent code/release evidence, NOT installed rule state:** Hubitat-local-MCP-server [5.1.5 changelog](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/main/CHANGELOG.md) documents native `Certain Time (and optional date)` rule triggers and `yyyy-MM-dd` date values. The upstream [NativeModelSpec.groovy](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/main/src/test/groovy/server/NativeModelSpec.groovy) uses `time#`, `atTime#`, `date#` and `atDate#` with `type=date`, validates the native page's `atDate1` field, and rejects mismatched text types, impossible calendar dates and numeric values. [NativeRuntimeSpec.groovy](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/main/src/test/groovy/server/NativeRuntimeSpec.groovy) also validates `atDate1` as a calendar `yyyy-MM-dd` date. The upstream `TOOL_GUIDE.md` set_rule_reference section does **not** spell out `atDate#` specifically, so v0.18.411's installed strict guide attestation being false is not contradictory. These upstream test cases are not evidence of installed saved date fields, live trigger execution or native writer safety.

**Decision:** v0.18.411 readiness routing and requested version cross-check acceptance PASSED; do not ship another response-format patch or lower the current `>=5.1.6` dated-authoring minimum from the upstream changelog alone. Native Rule Machine app 169 built-in type and parent-role proof from the prior v0.18.410 investigation still stands. The next distinct milestone is **read-only native trigger schema/readback evidence** from a real already-existing dated RM rule, if one exists; do not create/update/activate/delete rules or use native form-open writes simply to obtain that evidence. If no existing dated rule or native readback exists, report that limitation and prioritize a safe upstream schema/read capability rather than silently attempting an authoring test.

---

## 2026-11-05 — v0.18.410 native readiness preflight mispublished as app identity; v0.18.411 candidate

**User-observed failed acceptance:** Read-only native Rule Machine *dated one-time authoring readiness* question on installed HomeBrainOS v0.18.410 (3.413s UI; 0.658s agent, zero model rounds, 3 read-only MCP source calls and one local typed projection). The typed_native_rule_readiness details established **MCP initialize version 5.1.5**, latest hub-local backup **2026-11-05T03:02:31+00:00** (24 returned backups), both native tool-guide sections readable, `preflightEvidenceComplete=true`, and `readinessForMutation=false`. No rule or device changed.

**Root cause confirmed:** Shared read-only completion did not prioritize native_rule_readiness_coverage. The original question's reference to already verified *parent app 169* matched the generic app_class_identity keyword predicate; a second completion pass replaced the meaningful preflight answer with "Native class identity: not independently verified" and labeled previous identity observations "not-checked" for **this separate preflight turn**. Earlier v0.18.410 app-identity certification remains valid from its own receipts, not from the unrelated preflight.

**Additional requested evidence omitted in v0.18.410:** The direct readiness path had only initialize/serverInfo version, not the independently requested `hub_get_info.mcpServerVersion` comparison. The native guides were readable, but no typed `atDate#` date declaration or persisted date readback was certified. Therefore `preflightEvidenceComplete` should not be misrepresented as complete *authoring* readiness.

**v0.18.411 candidate:** Add early shared-completion specialist precedence using the already published typed native readiness receipt. Preserve original preflight answer and domain. Optionally read `hub_get_info` exactly once when the user explicitly requests version agreement; project missing/conflicting values. Track requested atDate# guide declaration and readback as independent evidence requirements, leaving unverifiable values unknown and `readinessForMutation=false`. Simple readiness keeps three source calls. The upstream changelog reports date support as of MCP 5.1.5, but HomeBrain's installed native writer still requires >=5.1.6; do **not** lower that threshold or create/delete any rule without a separate proven contract and explicit confirmation. See `hubitat-mcp-ai/CHANGELOG-0.18.411.md`. CI and installed post-update acceptance pending.

---

## 2026-11-05 — installed v0.18.410 native app identity acceptance PASSED; writer remains blocked

**Observed installed read-only acceptance, same exact-ID request SHA** `b0050c45bb76df89ec7f550f731d248a8765f59faea6cbf97ab884a1e70d924a`: HomeBrainOS **0.18.410**, 26.682s total, 8 free Gemma 31b rounds, 4 successful nonmutating MCP calls, 23.433s provider, 1.092s MCP execution, no paid rounds. Read-only typed receipts verify installed Rule Machine app **169** has **appTypeId=18** (user=false, parentId=null); the Hubitat-sourced type-catalog **id=18** reports **name=Rule Machine, system=true, isBuiltIn=true** (catalog also lists distinct legacy type 19); target-matched app configuration confirms **parentAppId=null** and **42 child-app rows returned in one page**. Do not convert child rows into a complete rule inventory, and do not invent a type namespace that is absent from the typed catalog receipt.

**Acceptance:** The final answer explicitly separates verified built-in **app-type identity**, source-observed root/parent relationship, and still-unverified **Rule Machine writer**. `metrics.outcome=success`, `investigation_coverage.status=source-checks-complete`, `evidenceComplete=true`, `questionResolved=true`, `instance_identity=observed`, `native_class_binding=observed`, `appIdentityCorrelation.nativeClassBindingVerified=true`, `nativeParentRoleObserved=true`, and **`nativeRuleWriterAuthorized=false`**. v0.18.410's defined identity-domain quality acceptance **passes**; no further identity-specific release is required merely to repeat this conclusion. This is observed product behavior, not first model-delivery or deployed commit-SHA certification (all three provenance flags remain false). The 26.682s vs previous 29.962s is one uncontrolled observation and does not certify speed improvements.

**Residual Technical JSON consistency gap:** `hypothesisComparisons[*].discriminator_verified=false` and `hypothesis_verdict=unverified` still reflect the model-proposed/earlier proof stage even though the deterministic final coverage verifies the built-in type. The generic `completionNote` and `stopRule` also retain pre-proof wording. These should be labelled **pre-publication model hypotheses** or reconciled with the certified domain-specific result in a general reporting pass; do not re-open the proven identity issue or change actual evidence.

**Next project gate — native dated one-time Rule Machine creation (NO WRITE AUTHORIZED):** Upstream [MCP issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) is closed; upstream [CHANGELOG v5.1.5](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/main/CHANGELOG.md) explicitly says `hub_set_rule` accepts `date` inputs (`atDate#`) for `Certain Time (and optional date)`, with yyyy-MM-dd values and readback. However `rule_authoring_service.py` and `native_switch_schedule.py` currently require installed server >=**5.1.6**, so upstream documentation and HomeBrain's conservative version threshold differ. Do NOT lower the threshold or claim installed support without a verified read-only MCP initialize/serverInfo version, matching current `hub_get_info.mcpServerVersion`, installed guide contract and if available a genuine native form/readback source. Parent *identity* is now source verified, but RuleAuthoringService's own `_native_parent_id()` preflight still uses a different unfiltered inventory + summary protocol; inspect for possible false negatives without bypassing any confirmation/backup/date/duplicate safeguards.

**Next read-only acceptance request:** Check installed MCP Rule Server version from initialize plus `hub_get_info`, native `set_rule_reference` guide, current hub-local backup timestamp, read-only type/instance parent evidence and any existing native dated trigger's `atDate#` fields; report evidence and gaps. No `hub_set_rule(operation=create/update)`, `hub_set_native_app`, confirmation, device command, router block or test rule create/delete without separate explicit authorisation. A writer contract is a distinct authorisation domain even after successful identity certification.

---

## 2026-11-05 — v0.18.409 installed live built-in type ID binding; 0.18.410 candidate

**New live source evidence:** Installed HomeBrainOS **0.18.409** on the same read-only instance/type correlation question yielded **29.962s**, eight Gemma Cloud rounds, four read-only MCP calls (provider 25.999s). No device or rule change. Current-turn typed receipts show exact installed app **169** with appTypeId **18**, type `Rule Machine`, user=false, parentId=null; an exact source-backed type-catalog row **id=18** with name `Rule Machine`, system=true, isBuiltIn=true; another catalog row id=19 `Rule Machine Legacy` (separate type, correctly not joined); and a target-matched app config with parentAppId=null and 42 returned child-app rows. Type-catalog source `hub_api`, projection untruncated, no next cursor. No source-level namespace reported in the type record; don't invent it. Source-defined built-in classification is more specific and higher value than name-based inference.

**Detected conservative-calibration false negative:** v0.18.409 marks `instance_identity=observed` and `typeIdJoinObserved=true` but continues to report the native type identity as unverified due to an older pre-ID-catalog assumption. The exact hub-provided type ID matches a built-in catalog entry, which **does source-verify built-in type membership**, while separately confirming the target is a root with returned children. Neither proves native Rule Machine authoring capability, dated trigger fields, rule creation safety or a rule writer contract.

**0.18.410 candidate:** Treat exact-ID, unambiguous built-in catalog class match as verified native type membership when all source guards pass (consistent type name, system/isBuiltIn true, instance user false). Separately require matching root and child-app observations to establish the reported parent role. Only when both are present mark app identity domain complete. Continue publishing a bounded, receipt-backed narrative and record `nativeRuleWriterAuthorized=false` in `appIdentityCorrelation`. Incomplete or contradictory sources remain unresolved. No permission or writer changes. Installed acceptance and latency still pending; consult `hubitat-mcp-ai/CHANGELOG-0.18.410.md`.

---

## 2026-11-05 — installed 0.18.408 exact-ID app class investigation and candidate 0.18.409

**Observed test:** The user executed a more explicit read-only app 169 instance→type correlation prompt on installed HomeBrainOS **0.18.408**. Elapsed 28.661s (UI 28.7s), 8 free Gemma rounds, four successful read-only MCP calls; provider 24.483s, MCP HTTP 1.267s. No mutation. The new request SHA `b0050c45...` differs from the previous app identity question, so the latency difference is not a controlled version benchmark.

**Source coverage defect:** Model-selected `hub_list_apps(scope='instances', nameFilter='Rule Machine')` and `hub_list_apps(scope='types', nameFilter='Rule Machine')` returned only generic root field-name Technical JSON receipts. A separate target-matched `hub_get_app_config(appId=169,summary=true)` receipt established reported `type='Rule Machine'`, `namespace='hubitat'`, `user=false` but did not expose the requested numeric `appTypeId` or independently matching type-catalog class. The final answer was correctly **unresolved**. Native Rule Machine writer remained blocked.

**Upstream source path:** Upstream issue #526/PR #527 and v4.7.1 source code specify `appTypeId` in `hub_list_apps(scope='instances')` rows and a `scope='types'` class catalog with type ID, namespace, `system`, `isBuiltIn`. The current user's actual target type ID and matching catalog row have **not yet been inspected as typed evidence**.

**0.18.409 candidate:** Add narrow typed receipt projections for successful, explicitly name-filtered app-inventory and type-catalog reads, with exact numeric ID joins, no name-only matching, source tags, bounded page rows and strict read-only validation. Shared completion may mark **instance-to-type ID observed** when the source-returned target app row includes a valid numeric type ID, while still leaving the independently certified **native class/parent** relationship unverified; show the exact catalog ID match and reported built-in flags only if they appear in matched typed catalog records. No extra model calls, MCP requests, rule writes, code execution or changes to permission gates. CI and installed acceptance pending; see `hubitat-mcp-ai/CHANGELOG-0.18.409.md`.

---

## 2026-11-05 — installed v0.18.408 acceptance PASS for read-only source-backed app-identity answer

**Installed evidence (app instance 169, same normalized request SHA):** version 0.18.408; total response **25.153s**, 5 free Gemma 31b rounds, 3 MCP read-only calls, **21.828s provider time**, 1.286s MCP execution, 1.501s MCP HTTP. Provider time is the dominant cost. This individual run took about 6.014s more than the single installed 0.18.407 sample (19.139s) while preserving the same 5 model rounds and 3 MCP calls; do not infer a systematic latency regression from two observations.

**Acceptance confirmed:** A target-matched `hub_get_app_config(appId=169)` receipt of kind `typed_app_instance_metadata` reports name and label **Rule Machine**, explicit `parentAppId=null`, **42 child-app rows returned in one page**, `nativeClassBindingVerified=false`. The published answer repeats exactly those source-reported facts, expressly says the child-app page is not a complete rule inventory or child-type attestation, and leaves native class/parent verification **unresolved**. `app_identity_source_publications=1` and `appIdentityPublication.mode=bounded-source-identity-publication` confirm the actual v0.18.408 read-only publisher ran. No mutating receipt. Independent instance-to-type identity and native-class binding both remain `checked-unverified`; the projection did **not** include an `appTypeId`. The result does not certify first-model delivery or deployed build SHA: provenance flags stay false.

**Source capability discovery (upstream source audit, not a user-hub read):** The upstream [Hubitat-local-MCP-server issue #526](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/526) is closed; [changelog v4.7.1](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/main/CHANGELOG.md) records that `hub_list_apps(scope='instances')` includes `appTypeId` from `/hub2/appsList`. In upstream `libraries/mcp-code-management-lib.groovy`, `toolListInstalledApps` projects app instance `id`, `type`, `appTypeId`, `parentId`, `user` and child counts, but results are paginated at 50 rows and may be name-filtered. Separately, `scope='types'` returns catalog rows with `id`, `namespace`, `name`, `system`, `isBuiltIn` derived from built-in / community type catalogs. An `appTypeId` exposed by the hub would permit an ID-based cross-source comparison without ambiguous name-only matching. These are documented upstream capabilities, **not proof that this user's current installed version returned appTypeId for app 169**, nor yet a verified formal class binding.

**Next evidence-first step (no code release automatically authorized):** run a bounded, read-only `hub_list_apps(scope='instances', nameFilter='Rule Machine')` (page across cursors when necessary) and inspect the exact app ID 169 row for numeric `appTypeId`, `type`, `user`, `parentId`; separately read `hub_list_apps(scope='types')` (page all if needed) for the matching type ID, name, namespace, `system`, `isBuiltIn`, and source-coverage notes. Do not infer completeness from a first page; do not claim type binding from names. Only design/implement a conservative typed identity correlation from the actual returned shapes after confirming the current MCP deployment's response; native Rule Machine **writer** stays fail-closed independently of identity.

**Decision:** v0.18.408 source-publication correction passes its defined live quality criteria. Stop cosmetic answer-fixing releases; focus on obtaining missing native class evidence using existing upstream read-only MCP capabilities.

---

## 2026-11-05 — installed v0.18.407 live app-class result and v0.18.408 source publication

**Observed live:** `/api/ask` for app 169 native parent class on reported installed HomeBrainOS **0.18.407**: 19.139s total, 5 Gemma free rounds, 3 MCP reads, 15.427s provider, 0.871s MCP agent, 1.114s MCP HTTP. Same exact normalized request SHA as prior tests. This individual result is faster than prior 0.18.405 (22.568s) and v0.18.406 (36.567s; 52.189s) samples, but these uncontrolled tests do NOT prove a latency regression or improvement.

**Positive advancement:** Technical JSON contains actual source-typed `typed_app_instance_metadata` from `hub_get_app_config(appId:169)`. It attests `reportedLabel=Rule Machine`, `reportedName=Rule Machine`, explicit `parentAppId=null`, and **42 `childApps` rows in returned page**, with `nativeClassBindingVerified=false`; no appTypeId, source-reported namespace/type or reportedSystem is in that published receipt. Coverage remains `app_class_identity`, both `instance_identity` and `native_class_binding` checked-unverified. There were no mutating tool calls.

**Remaining failure:** Model answer said `system:true` was explicitly marked, asserted **41 child rules**, and said all were `Rule-5.1`. This goes beyond published typed evidence. Not a proven hallucination: source raw payload may include extra details; 42 child-app rows need not all be rules. But public evidence does not authorize the definitive system flag, rule-total, or rule-type statements.

**v0.18.408 general correction:** For the independent app-native-class verification domain, when binding is incomplete, produce a concise source-typed public answer from bounded target-matched current-turn receipts, not individual unreliable regexes for unsupported assertions. Preserve reported name, type, namespace, flags and child-app returned-page counts only when actually attested; never upgrade child-app rows to rule inventory, self-reported root to native class, or partial type catalog to full binding. Preserve model-driven source selection; no additional MCP/model rounds or writer authorization. New Technical JSON marker `appIdentityPublication.mode=bounded-source-identity-publication`. CI and installed post-update result pending. See `hubitat-mcp-ai/CHANGELOG-0.18.408.md`.

---

## 2026-11-05 — v0.18.406 live app-parent acceptance: summary-shape gap and unsupported native certification

The user's installed 0.18.406 free Gemma Cloud investigation of app 169 ran **36.567s**, **8 model rounds**, **5 read-only tool calls**, provider **31.994s**, MCP HTTP **1.705s**. Compared with v0.18.405's one 22.568s/5-round/3-read sample, it was slower in this individual run, chiefly from increased model time; no controlled regression is established.

The answer remained on-topic but **overstated certainty**: it said app 169 was *verified native/built-in*, and assigned appTypeId 18, while the Technical JSON still recorded `app_class_identity` with `instance_identity=checked-unverified`, `native_class_binding=checked-unverified`, and `outcome=unresolved`. Positive claims of independently certified native class identity are not supported by the published receipts. This does not prove the model hallucinated the appTypeId because raw MCP source payloads may have supplied it.

**Source-shape root:** The selected `hub_get_app_config({appId:169,summary:true})` returned a flat `id/name/type/user/namespace` summary with no appTypeId and no nested app. The 0.18.406 projector handled only a nested app with appTypeId, so emitted only a generic field-name receipt. The other inventory/type-catalog reads also emitted field names, not a matched authoritative class binding.

**v0.18.407 candidate:** Accept both exact-ID-scoped nested/full and top-level/summary metadata as bounded typed **reported** fields. A missing type ID remains a partial source receipt, not verified instance-to-type mapping. A final read-only claim-calibration guard detects affirmative unsupported native certification and repairs it using only matching typed receipts, preserving calibrated model prose without any extra reads or model rounds. Rule writing remains closed. See CHANGELOG-0.18.407.md. Installed after-update quality and latency have not been measured; no first-model delivery/deployed-SHA attestation.

---

## 2026-11-05 — v0.18.405 live app-parent acceptance: relevance fixed, public scalar receipt gap remains

The user supplied installed HomeBrain v0.18.405 live read-only natural-language answer and full Technical JSON for app 169. Reported runtime **22.568s**, **5 Gemma Cloud rounds**, **3 MCP read-only calls**, **1 discovery call**; free allowance, no paid rounds, no modifying receipts. The earlier v0.18.404 test was 33.825s, 7 rounds, 4 reads. One before/after pair cannot certify systemic latency improvement; provenance still reports model_delivery_verified=false, first_attempt_verified=false, deployed_build_sha_verified=false.

**Success:** The live answer now directly separates displayed app name, reported app type, parent/system metadata and the separately unverified native Rule Machine class relationship. Technical coverage domain is **app_class_identity**, both obligations **checked-unverified**, outcome **unresolved**. The prior unrelated rule-action and inactivity-OFF checklist is absent. PR #1427's routing/publisher objective is supported by this observed test.

**Remaining limitation:** The model answer says label and name are verified, reports Rule Machine in hubitat namespace, system=true, parentAppId=null and 42 child rules. The published receipts contain only success, tool name, target ID and response **field names** (not those identity scalar values). It is therefore not possible to audit those particular positive factual claims from the supplied Technical JSON. Do **not** call them hallucinations, because the model may have inspected the raw MCP output. The logically correct native parent verification remains **unresolved**; display labels, system/root status and reported children are not authoritative native class attestation.

**v0.18.406 candidate correction:** Add an allowlisted, read-only, target-identity-matched typed receipt from hub_get_app_config, keeping source-reported ID/appTypeId separate from independently attested native class identity. Preserve only safe scalar metadata and returned-page child row count; never copy arbitrary settings/HTML or unlock rule writing. The existing evidence plan can then mark instance identity **observed** only if actual app ID and appTypeId are source-projected. Native binding remains checked-unverified until a separate authoritative class mapping exists. See CHANGELOG-0.18.406.md. No post-v0.18.406 installed result yet.

---

## 2026-11-04 — v0.18.405 general app-class identity fix merged, live acceptance pending

**Merged production-code fix:** [PR #1427](https://github.com/ienam-smarthome/HomeBrainOS/pull/1427)
tested exact head `5207a97ee09516aed296ce43f1b00dda7388a8f7`,
merged commit `2b2f146df22d2539ab0effd352670bf458f0dd79`.
All four required workflows passed: Hubitat MCP AI tests,
Validate HomeBrain OS, Release assurance and Answer
Quality scorecard integrity. The dedicated add-on and
full release Python suites each reported **6,477 tests
passed, 2 warnings**; metadata and container smoke green.
Earlier failing PR attempts were corrected, including
README/changelog version synchronisation and a pytest
reserved-param test name. A cancelled intermediate CI
run was **not** counted as success; the final exact-head
four-workflow gate is all-green.

**Change:** Native installed-app **class/parent identity**
read questions are separated from installed-rule
**executable action-tree verification** in model-advisory
interpretation, deterministic scope, evidence obligations
and shared completion. Generic read success and field
names cannot certify native class membership; an
incomplete type catalog does not prove a type missing.
The old stored-logic guard now cannot replace a
class-identity explanation with generic inactivity-OFF,
duplicate-rule and nested-IF boilerplate, even if it
sees a stale old rule-audit coverage label. Combined
requests explicitly asking for compiled triggers
and ordered actions retain the strict installed-rule
contract. No new inference/tool call, auto-write,
native writer enablement or hub state mutation.

**Critical deployment boundary:** PR merged to main
and add-on **source version v0.18.405** is available;
the user's reported **installed runtime was v0.18.404**
during the failing 33.825s/7-round/4-read live test.
**No installed v0.18.405 acceptance sample yet.**
Do not say the source fix has improved end-to-end
latency, resolved class identity, or solved upstream
MCP Rule Machine parent verification without new
read-only evidence. The four-domain offline Qwen/Llama
results and one Gemma Cloud MQTT result remain
separate; no official blinded human scores or
Claude parity have been established.

**Next action:** User updates Hubitat MCP AI add-on
to v0.18.405 in Home Assistant, then asks exactly
one read-only question: "Investigate whether Rule
Machine app instance 169 is independently verified
as the native Rule Machine parent. Separate the
app's displayed name, its app-type identity, and
any independently verified native class relationship.
Explain what remains unverified and what read-only
evidence would resolve it. Do not create, modify
or execute any rule." Obtain full answer and
**Technical JSON**; check intended
`app_class_identity` domain, non-certified
parent proof if typed mapping is absent,
no unrelated rule-action boilerplate,
tool/round counts, and total wall time.
No rule writer or devices should be touched.
If v0.18.405 still fails, investigate its actual
typed receipt/plan/publisher path before another
fix; avoid incident-specific patches.

---

## 2026-11-04 — first live Rule Machine native parent-identity test: scope/publisher defect; v0.18.405 correction pending acceptance

**Actual user-provided installed HomeBrain v0.18.404 read-only
sample at 23:39 UTC:** Asked whether installed Rule Machine
app instance **169** is independently verified as its native
parent. Original request requires distinction among display
label, appTypeId, built-in namespace/class and direct
source-attested native parent identity; explicitly forbids
creating, modifying or executing a rule.

HomeBrain produced an **unresolved**, off-topic
`existing_rule_verification` report enumerating ordered actions,
nested IF, duplicate rule names, inactivity-OFF controller
duration, delays and command execution. The main requested
native parent/class identity was not addressed directly.
A successful `hub_get_app_config(appId=169)` or
`hub_get_rule_health(appId=169)` read cannot by itself
establish a native type/class relationship when public
evidence receipts expose only **field names**, not
typed mapping values.

**Diagnostic metrics:** model `gemma4:31b`, free Ollama
allowance reported, **33.825s** end-to-end,
**7 model rounds**, **4 MCP read-only calls** (two
`hub_list_apps`, one `hub_get_app_config`, one
`hub_get_rule_health`), provider ~**26.299s**.
The Technical JSON did correctly retain both
class hypotheses with `discriminator_verified=false`,
`hypothesis_verdict=unverified`, but published
an irrelevant canned report. Reported outcome `unresolved`
is appropriately cautious. No modifying tool was recorded.
Request diagnostics have `model_delivery_verified=false`,
`first_attempt_verified=false`, and
`deployed_build_sha_verified=false`; **do not**
grade verified production first-attempt reasoning or
claim the exact installed build SHA beyond v0.18.404.

**Root-cause code path:** the advisory/model interpretation
and `investigation_intelligence` used the
`existing_rule_verification` plan for an **app class
identity** question. Its `stored_logic` requirement
was unverified (correct for the wrong scope),
and `existing_rule_claim_guard.calibrate_existing_rule_verification`
replaced the useful question's result with a
prewritten action-tree/controller checklist. This is a
**task/scope and publication problem**. It does not prove
Hubitat/MCP lacks native parent data, or that Gemma
would independently produce a correct answer from full
typed evidence.

**Pending v0.18.405 generalized fix:** Distinguish native
installed-app type/parent **identity** from an actual
rule's executable trigger/action audit, both in the
advisory objective and the final proof contract.
Do not mark identity verified from a display label,
catalog omission, generic `success:true` or tool
field-name list. Prevent stale action-tree coverage
from overwriting identity answers. Protect existing
stored-rule audits and preserve the no-write policy.
Add targeted regression tests and require all CI green.
See `hubitat-mcp-ai/CHANGELOG-0.18.405.md`.

**Next after merge/update (not yet measured):**
Install the newly released add-on and repeat this
single **read-only** app 169 native parent-identity
question with full answer + Technical JSON. Record
correct objective, evidence coverage, model/tool rounds,
end-to-end time and whether answer focuses on
native class rather than unrelated rule logic.
If source identity is still unverified, **say so**;
do not enable any Rule Machine writer. Existing
four-case offline Qwen/Llama outcomes stay independent;
no Claude-like or target accuracy claims.

---

## 2026-11-04 — Rule Machine Llama local saved-file SHA discrepancy resolved

User reopened the original private local Q2 Rule Machine parent
capture directory and ran PowerShell `Get-FileHash` on
`aq_rule_parent_type_gap.candidate.txt`. The **actual saved
file's SHA-256** is
`b8ee24d20674fb6d932027d11188cdc81e8b8d4b1078ea84ea5ecf8d221d5ca6`,
**exactly matching** `candidate.json` for local
`llama3.2:3b` on packet
`21542170532d34510b19613f6c7bd97958cf300aa8cf151e2649ef8328b14cf3`.
The user's `Get-Content -Encoding UTF8 -Raw` showed the same
substantive answer as the earlier paste. The former assistant
hash over pasted text differed because its **representation**
was not byte-identical; **the saved benchmark answer is not
shown to be corrupted**. The earlier Q2 status's "integrity
discrepancy" is **superseded** by this original-file
verification. The original-file hash and manifest are
verified by the user's local check, not independent
provider attestation, and it does **not** prove Llama's
reasoning correctness.

All **four local Q2 domain pairs** now have complete
user-observed outputs and the Rule Machine file-integrity
question is closed. Evidence-based qualitative judgments
remain unchanged: Qwen more source-complete but speculative;
Llama faster but incomplete or causally wrong on several
cases. Blinded SHA-bound human grades, overall grounding
percentages, provider comparison beyond one Gemma Cloud
MQTT case, and actual HomeBrain end-to-end metrics are
**NOT MEASURED**.

**Next step:** One *read-only live HomeBrainOS*
investigation of native Rule Machine parent identity
(app 169) with complete natural-language answer and
Technical JSON. Do not create/modify/execute rules,
change existing model routing or infer native class
identity from an app display name. No new offline
inference required. Add-on remains **v0.18.404**.
[Updated four-domain review](ANSWER-QUALITY-Q2-FOUR-DOMAIN-LOCAL-REVIEW-20261104.md).

---

## 2026-11-04 — Q2 fourth local Rule Machine identity case completed; four-domain descriptive review, no formal score

**Actual Windows local A/B on the final four-case-set domain:**
`aq_rule_parent_type_gap`, source packet
`21542170532d34510b19613f6c7bd97958cf300aa8cf151e2649ef8328b14cf3`,
recorded checkout SHA `659d3a3e3373b654a54439b37461a9e237aa2289`,
one requested first answer per arm.
- **Qwen3.5:4b local:** 19.657s, saved answer SHA
  `3511c0f2604d4cbfcb0e5d7e1e76deb8ca9a3a776bc4a56d87a1fcf5af17aa96`.
  Exact user-pasted UTF-8/LF text SHA matches; notes app 901/type 718
  and incomplete built-in catalog but only suggests full catalog, rather
  than direct source-attested native writer class identity.
- **Llama3.2:3b local:** 8.297s, manifest answer SHA
  `b8ee24d20674fb6d932027d11188cdc81e8b8d4b1078ea84ea5ecf8d221d5ca6`.
  Pasted visible text provisionally concludes not verified but
  speculates that system fails to recognise type and lacks explicit
  native-class identity requirement. **Integrity discrepancy:**
  exact visible pasted text SHA computes as
  `f88b1baf1eb1ead58147fb778a4b91ec7138b7ed933acc8abe631ff2c783b346`,
  **not** the recorded manifest hash; user should locally
  `Get-FileHash` the saved original before any SHA-bound grading.
  Do not silently call this response hash-verified.

**Four distinct local Qwen-vs-Llama frozen pairs now exist**
(MQTT, command-off provenance, heating restoration, native RM identity).
Four-sample descriptive arithmetic means of *model-only* latency:
**Qwen 22.254s**, **Llama 8.457s**, ratio ~**2.63×**
(by total wall times). Llama is faster in all four, but missed
important evidence in MQTT, heating and the RM explanation and
made contradicted causality claims on the command case.
Qwen generally covered more source facts but also speculated
and issued unsupported causal/execution implications;
one Qwen issuer answer visibly ended mid-heading. **Neither
model has demonstrated reliable first-answer correctness
or Claude-quality reasoning.** Across-case runner SHAs changed;
only within-pair packet/settings equality is verified by
tool metadata. Do not extrapolate measured latency p95,
operational HomeBrain times or model SLA.

**Quality status:** Source-based assistant qualitative review only,
not a blinded or independently completed human SHA-bound review.
Official grounding >=90%, useful-first >=80%, unsupported
causal-claim rate, Gemma/Claude gap and p50/p95 continue
**NOT MEASURED**. Keep installed add-on **v0.18.404**,
production routing and device rules unchanged. Next: check
original Llama saved text hash; seek real SHA-bound human
reviews and one **read-only live HomeBrain answer + technical
JSON** before implementation changes. Paid Gemma cross-domain
calls require explicit separate authorization. Avoid
single-device publication patches.
[Four-domain source and limitation review](ANSWER-QUALITY-Q2-FOUR-DOMAIN-LOCAL-REVIEW-20261104.md).

---

## 2026-11-04 — Q2 heating restoration first answers: complete capture, Qwen speculative and Llama incomplete

**Actual Windows local first-answer pair** on `aq_early_heating_off_resume`;
one case, one model invocation per arm, no cloud or device calls.
Same frozen evidence packet SHA
`cb5153f5d4beb82491c34b619d8e64f8f46bec86962533db38ffb4124e8a3bb1`,
checkout SHA `7e81e0411b50f814241a64c2406f7fe908fa95fd`,
recorded attempt index 1 for both arms.

- **Qwen3.5:4b local**: **22.672s**, answer SHA
  `ea47ab547ef37fc6cc61e73f3cb8b46c312fc335451650cd9d41143988b0cb66`.
  Correctly describes lowering the selected thermostat/TRV to 12°C,
  restoration to 22°C at 30 minutes, and independent heat demand/protection,
  but speculates on frost-protection floor and timer heartbeat
  without evidence; does not explicitly separate target temperatures
  from physical boiler operation.
- **Llama3.2:3b local**: **6.406s**, answer SHA
  `3da98ab387346a8b666f36b35ecdb0e63e9431be3d701658518b4a44b8ca9f1e`.
  Provides only the initial 12°C override. Omits restoration,
  separate demand logic and physical operation limitation:
  **not a useful complete first answer**.
  Llama was **16.266s faster** (~71.7% shorter model-request
  latency) on this single local case, but speed is not accuracy.

Both saved first-answer hashes were independently reproduced
from user-pasted plaintext by correcting the **display-only**
PowerShell mojibake `Â°C` to actual UTF-8 `°C`.
Use `Get-Content -Encoding UTF8 -Raw` when displaying the
private files on Windows; no output changed and no private
responses were committed. The run records do not retain the
server `done_reason`: do not guess why Llama stopped
after one sentence.

**Qualitative review only**, source-grounded against
the existing versioned heating packet; no independently
attested SHA-bound human grade, no formal model accuracy,
useful-first-attempt percentage or production HomeBrain latency.
No generic runtime prompt/patch or provider switch justified
at this stage. Proceed with one local frozen
`aq_rule_parent_type_gap` pair in a new external
private folder, then compare the *four source domains*
before considering general model/evidence/publisher
improvements. HomeBrain add-on stays **v0.18.404**.
[Full heating case review](ANSWER-QUALITY-Q2-LOCAL-HEATING-PAIR-20261104.md).

---

## 2026-11-04 — Q2 explicit token-limit first-answer gate merged; issuer-vs-reporter results documented

**Exact-head verification:** [PR #1422](https://github.com/ienam-smarthome/HomeBrainOS/pull/1422),
tested head `9b2fceef1bc90585a6734b5d9b945be85986298b`,
merged commit `82540290f2400e2f792fd98ed63fe2545ab30daf`.
All required CI passed (Validate HomeBrain OS, Release
assurance, Answer Quality scorecard integrity). Full
Python suite: **6,466 tests passed, 2 warnings**.
Metadata validation and add-on container smoke checks green.

**User's completed frozen `aq_command_issuer_vs_reporter`
local A/B (same source packet and checkout SHA):**
Qwen3.5:4b **26.344s**, answer digest
`a5479755e6b750941a1a283d00bdcc0ee1f90e31600f2c9e1008a239327fc064`;
Llama3.2:3b **10.594s**, digest
`fe3bdf3ce62350edf2d00de3d51ae501a26b0b84e612ce81a439807369a305c2`.
Both exact saved text hashes verified. Qwen identified issuer
4012 vs Hue reporter but overclaimed a confirmed command
receipt/bridge causal chain and its saved answer stopped
mid-heading. Llama falsely inferred prior physical OFF
and command delivery and confused notified listener with
the separately recorded command issuer. This is **one
source-based qualitative review**, not a blinded human
grade or production provider recommendation.

**General evaluator safety fix:** Accept `done:true` as
first-answer completion only if provider does not
explicitly report `done_reason=length` or an
unexpected stop reason. Preserve compatibility with
providers omitting optional `done_reason`, but
absence does not prove complete prose. No retry,
no extra cloud use, no higher output cap, no
changed source packet. Qwen's historical `done_reason`
was **not captured**, so its token-budget explanation
is still a hypothesis, not a known provider reason.
No live Hubitat/HA/devices/rules changes and no
production add-on change; v0.18.404.

**Next Q2 gate:** One fresh *local-only* Qwen/Llama
run of `aq_early_heating_off_resume`; inspect
actual answers, hashes and safe errors. If a model
explicitly reaches a token cap, mark that run as
incomplete rather than silently repeating or
changing token settings. Follow with the
`aq_rule_parent_type_gap` case. Factual grounding
percentages, useful-first response rates,
Gemma/Claude gap and p50/p95 remain
**NOT MEASURED** without independent
SHA-bound review and adequate sample count.
[Full command provenance case](ANSWER-QUALITY-Q2-LOCAL-COMMAND-ATTRIBUTION-20261104.md).

---

## 2026-11-04 — Q2 command OFF provenance: real local answers reveal two causal errors and truncated Qwen output

**New actual user-executed frozen local A/B:** `aq_command_issuer_vs_reporter`,
packet SHA `fbe2452406077b244438396d54a73636d43b0f1d30212597c97c54c9798ba0ea`,
checkout SHA `25a09d0ed5cd3f0bfdd2aac20147f50a0d719c29`.
Both actual first-answer plaintexts were supplied and independently
SHA-256 matched to the user-provided manifests (LF, no trailing newline).
No Hubitat/HA tools, cloud models or real automation writes.

- **Qwen3.5 4B local**: **26.344s**; answer hash
  `a5479755e6b750941a1a283d00bdcc0ee1f90e31600f2c9e1008a239327fc064`.
  Recognises app 4012 as command issuer, bridge as OFF reporter
  and app 4012 as a notified report listener; nevertheless
  infers bridge update from a received command without
  evidence of physical delivery, invents possible integration
  detail, and the **saved output stops mid-heading** at
  `**Most Useful Next Read` (digest-verified).
- **Llama3.2 3B local**: **10.594s**; answer hash
  `fe3bdf3ce62350edf2d00de3d51ae501a26b0b84e612ce81a439807369a305c2`.
  Conflates the report's listener with the separate command
  issuer and falsely claims the device received the command,
  was already OFF at receipt and app 4012 did not initiate
  the OFF command. Contradicts the actual source record.
  Llama was **15.750s faster** (~59.8% less wall time)
  for one model-only request, not a quality victory.

**New generic measurement defect discovered:** The private capture
tool accepted `done:true` with nonempty text, but did not check
Ollama `done_reason`; explicit `length` indicates a token-limit
stop that can yield coherent-looking but incomplete text.
Qwen's **historic provider stop reason was not recorded**:
the truncated original is proven, but `length` is only a
plausible explanation, not verified history. Candidate offline
tool fix rejects explicit `length` and unexpected reasons
without adding inference requests, changing `num_predict=320`,
cloud policy or the original frozen packets. Old clients
without done_reason remain compatible, without certifying
they stopped normally. Tests cover local/cloud scenarios,
normal stop, absent reason and safe error attribution.

**Review status:** Preliminary assistant source review only.
No separately completed/blinded human SHA-bound rubric;
official Q2 accuracy, first-answer completeness metrics,
Claude/Gemma parity, and p95 **not measured**. Both observed
models have unsupported causal claims; no production provider
change justified. Next independent source domain is
`aq_early_heating_off_resume` as **one local-only pair**
in a fresh private folder after exact-head CI/merge;
then `aq_rule_parent_type_gap`. No Hubitat/HA/device/rule
changes; add-on remains **v0.18.404**.
[Detailed Q2 case review](ANSWER-QUALITY-Q2-LOCAL-COMMAND-ATTRIBUTION-20261104.md).

---

## 2026-11-04 — Full Gemma Cloud MQTT first answer independently matches saved SHA; source comparison reviewed

**Original answer integrity:** User now provided the complete
Gemma Ollama Cloud `gemma4:31b` baseline text.
Its UTF-8 SHA-256, calculated from exactly that text
(LF, no trailing newline), is
`5a09a7146dd7351168426851c6edbecb8e42663557b2de38d2cf972fa88b38ad`,
matching the prior private `baseline.json` answer digest.
This confirms the reviewed text is consistent with
the user-provided capture manifest, **not** independently
attested server model identity or prompt delivery.
The earlier pasted broker-log excerpt is **not** part of
this SHA-matched Gemma response: the matched answer
recommends inspecting the driver's `mqttStatus` source
definition.

**Actual first-answer qualitative comparison, same frozen
MQTT source packet:** Gemma was **0.828 seconds**
(Cloud) and Qwen3.5 4B **22.750 seconds** (local).
Both correctly distinguish a driver/broker session from
offline/stale endpoint telemetry and avoid a verified
physical root cause. The **Gemma response omits** the
supplied driver's watchdog-written `lastActivity` with no
endpoint messages; the **Qwen response covers** this
important discriminator. Gemma is clearer and substantially
faster on this request; Qwen is more evidence-complete.
Their proposed next checks (driver source definition
versus broker session logs) answer different limited
questions; neither by itself verifies fresh endpoint
telemetry or physical power/connectivity.

**Boundary and next action:** This is a source-based
assistant qualitative review of one actual matched
frozen case; **not** an independently completed blinded
human SHA-bound scorecard. Official first-answer grounding,
usefulness, Claude parity and aggregate p50/p95 are still
**NOT MEASURED**. Do not change production model routing
or publisher based on one pair. Finish three *non-MQTT*
frozen Q2 cases, ideally one case per new local-only
private folder to avoid losing entire multi-case runs
to a single Ollama failure. No paid Cloud call, live
Hubitat/HA read/write, device or add-on change required.
[Full evidence review](ANSWER-QUALITY-Q2-FIRST-CLOUD-LOCAL-MQTT-20261104.md).

---

## 2026-11-04 — Q2 first actual Gemma Ollama Cloud vs local Qwen MQTT pair: latency measured, quality pending

The user ran a **one-case same-frozen-source first-answer
comparison** through the private-capture script:
`aq_network_broker_vs_device_health`, packet
`74ccff7fa2c23852655d12b45f6f5cbb6a3315de8c7647cac7b03441282f7150`.
Both metadata arms carry checkout SHA
`0e71f92f380d21cfb2d3a17a66fbd40d85bd0684`
and `attempt_index=1` (tool-recorded, not independently
authenticated provider delivery).

- **Gemma `gemma4:31b` on `ollama-cloud`**, baseline:
  **0.828s**, answer SHA
  `5a09a7146dd7351168426851c6edbecb8e42663557b2de38d2cf972fa88b38ad`.
- **Qwen `qwen3.5:4b` on `ollama-local`**, candidate:
  **22.750s**, answer SHA
  `2a1843c20024a7e83428a70de59d52dc5ef19f7a87beee341f73cf9bb7da60aa`.

Gemma was **21.922s faster** (~27.5×) for this one
model-only capture, not production HomeBrain latency or
a p50/p95. The Qwen answer digest exactly matches the
previous local MQTT Qwen answer (previously 20.344s),
consistent with identical first-answer content. The user
pasted only a **trailing excerpt** ending in a proposed
broker-log read-only check; the **full original Gemma
answer is not available in this turn**. Thus Gemma
factual grounding/causal-calibration/first-answer utility
and overall model superiority remain **NOT MEASURED**.
No blinded or human scorecard review, independently
verified source delivery or provider cost receipt.
Local Qwen answer-only thinking policy may differ from
Cloud Gemma default; source packets match, internal
provider execution settings are not independently attested.
The prior failed three-case local-only trial remains
a separate unresolved experiment.

**Next, no new inference needed:** user sends both
existing `<case-id>.baseline.txt` and
`<case-id>.candidate.txt` from this private cloud/local
run; privately grade against the fixed packet, then
expand into non-MQTT frozen domains. Do not select a
new production provider on a single faster result.
No code or add-on update; v0.18.404 preserved.
[Detailed evidence boundaries](ANSWER-QUALITY-Q2-FIRST-CLOUD-LOCAL-MQTT-20261104.md).

---

## 2026-11-04 — Q2 safe transport diagnostics merged, real three-case failure still unresolved

**Merged and exact-head CI:** [PR #1418](https://github.com/ienam-smarthome/HomeBrainOS/pull/1418)
tested head `2e859b73a4d665194cc6908f5a83cf50a40f83da`,
merged commit `170090a810bf637fd76d08c0e99266eae42360f1`.
All three required workflows passed: Release assurance, Validate
HomeBrain OS and Answer Quality integrity. **6,456 Python tests passed,
two warnings**; container smoke and metadata checks succeeded.
This is an **offline benchmark tool correction**, not a production
release; the HomeBrain add-on remains v0.18.404.

**Verified scope:** The Q2 private first-answer capture now identifies
a safely classified failure stage and, for model invocations,
the frozen case ID, candidate/baseline role, provider and
model. It distinguishes timeout, HTTP code, connection failure,
opaque provider/network fault and private-output filesystem errors.
Provider/OS exception details, raw answers, local file paths,
prompts, endpoints and secrets are not emitted. Unit tests validate
redaction for secret-bearing HTTP, URL, timeout and file exceptions.
Fixed source packets, local-only no-tool policy, cloud opt-in,
model settings, single-request/no-retry policy and private
output rules are unchanged.

**Live acceptance not yet observed:** The user's previous multi-case
attempt aborted with the old catch-all `private transport or file
error`. We do not know which case/arm or the environmental cause,
and no new complete human-reviewed pairs or accuracy scores were
received. The successful prior single-MQTT pair remains separate.
The next user action is to update their Windows local checkout,
run the same three-case selection in a fresh private directory
**once**, and share the two model outputs plus manifests if it
succeeds, or the safely classified failure if not. If the failure
is a timeout, plan a separately disclosed test within the existing
120–180s allowed timeout range. **Do not count this code
change as model quality, latency or Claude parity improvement.**

[Full Q2 source and limits](ANSWER-QUALITY-Q2-PRIVATE-FIRST-ANSWER-CAPTURE-20261104.md).

---

## 2026-11-04 — Q2 three-case local capture: opaque transport/file failure; safe diagnostic repair candidate

**Actual user observation:** Following the successful single
`aq_network_broker_vs_device_health` Qwen3.5 4B vs Llama3.2
3B pair, the user ran the next **three distinct frozen
synthetic cases** (issuer vs reporter, heating return, Rule
Machine native identity). The script returned
`Q2 capture incomplete: private transport or file error`
and did not provide paired first answers or scored outcomes.
The previous MQTT case stays valid. This error is the
tool's generic catch-all for a non-ValueError, including
local Ollama connection/timeout/provider failures and
private output filesystem errors; **the specific model,
case, stage and environmental root cause were not captured**.
Do not attribute it to Qwen, disk permission, network, or
memory without discriminating evidence.

**Proposed offline-tool correction:** Add a strictly
sanitized stage/category transport and file failure
type; preserve safe `case-id`, baseline/candidate and
model identity on failures; distinguish HTTP status code,
timeout, connection failure, opaque network/provider
failure and local private write error. Never print
exception bodies, raw answer, prompt, endpoint, auth
token or filesystem path. Preserve existing no-retry,
no-billing, frozen evidence, local/cloud segregation,
bounded timeouts, answer-only mode, and refusal to
overwrite prior private capture directories. Add
synthetic regression tests for security and attribution.
No changes to HomeBrain add-on v0.18.404 or Hubitat,
HA, router, devices or automations.

**Measurement boundary:** The multi-case run
**did not complete**; no additional reviewed Q2 pairs,
first-answer grounding, p50/p95 or model ranking are
established. Once exact-head CI green, user updates
checkout and runs the same three source packets in a
new private directory **once** to see either completed
first outputs or a safely classified failure. Avoid
increasing the timeout or running retries before
seeing which stage fails. Existing one-case MQTT
observation remains separate from this run.
[Error observability contract](ANSWER-QUALITY-Q2-PRIVATE-FIRST-ANSWER-CAPTURE-20261104.md).

---

## 2026-11-04 — Q2 first successful **actual** local-model frozen MQTT pair; preliminary review only

User completed the post-PR #1415 answer-only **local Ollama**
fixed case `aq_network_broker_vs_device_health` (new run,
not a recovery of the failed pre-fix attempt). Actual original
model answer texts were provided in conversation, alongside
private-output SHA metadata for both arms and a single
matched packet `74ccff7fa2c23852655d12b45f6f5cbb6a3315de8c7647cac7b03441282f7150`:

- **Qwen 3.5 4B**, baseline, `ollama-local`, **20.344s**
  response, answer SHA `2a1843c20024a7e83428a70de59d52dc5ef19f7a87beee341f73cf9bb7da60aa`.
- **Llama 3.2 3B**, candidate, `ollama-local`, **8.531s**
  response, answer SHA `e0cdb67452889dae74caa65122ba28907a605b56db245fb7060f54de163d6184`.

Both carry checkout SHA `0e71f92f380d21cfb2d3a17a66fbd40d85bd0684`
and self-recorded `attempt_index=1`. Measured speed delta:
Llama **11.813s faster (58.1% less time)** for this *one*
offline local request. No repeated-sample distribution and
not HomeBrain production wall time.

**Source comparison, not official human score:** Qwen correctly
separated broker connection and stale endpoint and included
the supplied watchdog-written `lastActivity` distinction,
but used a speculative background-process explanation and a
less targeted next read-only check (broker disconnect vs
genuine endpoint payload / watchdog `lastActivity`). Llama
answered the central MQTT/health contrast more briefly but
omitted the watchdog fact and next read-only discriminator.
Neither gives a verified physical root cause. No separately
authenticated/blinded human review was supplied;
formal Q2 quality score remains **NOT MEASURED**, as does
model-first provider attestation, Gemma/Claude parity,
p50/p95 and general model ranking.

**Next:** Stop repeating the MQTT case. Run the other three
unchanged frozen cases locally on the same pair: command
issuer versus reporter; early heating-off return; Rule
Machine parent/native identity gap. Retain fresh private
raw answers and hashes; review with the existing
SHA-bound rubric. No additional runtime/publisher
patch or model switch is justified.
[Full recorded review](ANSWER-QUALITY-Q2-FIRST-LOCAL-MQTT-PAIR-20261104.md).

---

## 2026-11-04 — Q2 local answer-only capability correction merged; actual A/B still pending

**Merged and exact-head CI verified:** [PR #1415](https://github.com/ienam-smarthome/HomeBrainOS/pull/1415)
fixes the offline Q2 first-answer capture's response-format/think-budget
hazard; tested PR head `40a4580effa4595f3f0ac55aeec86c9f4d7a7909`,
merged commit `7c2f1b5a6e3b944e3dcd2d1c4822a66467651d2f`.
All three required workflows succeeded, including **6,450 Python
tests passed (2 warnings)**, release assurance, container smoke,
metadata validation and Answer Quality integrity.

**Specific installed failure:** Windows local-model capture with
`qwen3.5:4b` and `llama3.2:3b` stopped on a generic no-final-answer
error. No exact failing model/raw provider response was captured, no
valid paired model answers were saved, and no semantic score resulted.
This failed invocation must not be counted as a completed first attempt.

**General repair:** After a local Ollama model inventory check,
`/api/show` supplies thinking capabilities. When a Boolean off
setting is supported, local `/api/chat` requests use the top-level
`think:false` setting, preserving the same frozen evidence,
temperature/seed/context/token budget, no tool definitions and
no retry. Nonthinking models do not receive the field. Other
thinking modes that cannot be switched off fail closed. Private
error messages now distinguish thinking-only, empty final text,
tool-call responses and oversized output, with safe arm
identification. **Cloud transport is unchanged**, and the add-on
remains **v0.18.404**.

**Important evaluation boundary:** This is local **answer-only**
first-output comparison, NOT an evaluation of thinking-enabled
model quality. All tests were synthetic/mock transport; no
actual Windows Qwen/Llama run after merge has yet been observed,
and Q2 factual grading, independent first-attempt provenance,
Gemma/Claude comparison and p50/p95 remain **NOT MEASURED**.
Next: user updates the local checkout and runs the same frozen
MQTT case once using a new private folder. Privately review
the actual plaintext and SHA-bound metadata, then continue
cross-domain Q2 fixed-evidence comparisons. No Hubitat, HA,
router, device, Rule Machine or production agent modifications.
[Detailed Q2 procedure](ANSWER-QUALITY-Q2-PRIVATE-FIRST-ANSWER-CAPTURE-20261104.md).

---

## 2026-11-04 — Q2 Windows local-only capture: incomplete model output, bounded candidate fix

**User-observed blocked first attempt:** From a valid local
HomeBrainOS checkout on Windows, user had installed `qwen3.5:4b`
and `llama3.2:3b`. The exact frozen MQTT case requested
one Ollama-local first answer from each. The capture exited
`Q2 capture incomplete: No bounded text-only first model answer`.
The original error groups empty final content, tool calls
and oversized response; **no proof identifies the failing arm**.
No completed pair, raw-answer files, quality grades, or real
first-answer latency comparison was established.

**General cause hypothesis:** Ollama /api/chat thinking models can
emit `message.thinking` separate from `message.content`; with
`num_predict=320` the budget may expire before final prose.
The tool did not set `think`; a thinking-only return is plausible
but not confirmed from that user's hidden provider envelope.

**Candidate non-runtime Q2 correction:** Probe each installed local
model's /api/show thinking controls. For a model supporting
Boolean off, send top-level `think:false` in its single /api/chat
request; omit for non-thinking models; refuse unsupported named-only
thinking controls rather than retry. Keep the same prompt,
temperature/seed/context/output cap, no tools, private answers,
no Cloud behaviour changes and no public capture. Distinguish
thinking-only and other incomplete outputs with a safe
model-arm-labelled error. This is an answer-only A/B mode,
not a scored thinking-enabled comparison. Code,
mocked tests and source-referenced review in
[Q2 private capture protocol](ANSWER-QUALITY-Q2-PRIVATE-FIRST-ANSWER-CAPTURE-20261104.md).

**Next live evidence:** If candidate CI passes, merge and rerun
the frozen MQTT *local-only* pair once in a new private folder.
Treat it as a fresh first attempt for the new run, not a recovery
or improvement score from the failed attempt. Then privately
review both exact model prose files against unchanged packet;
Gemma/Claude parity, published Q2 grounding and latency
distributions remain **NOT MEASURED**. No Hubitat/HA/router/device
or add-on runtime changes.

---

## 2026-11-04 — Q2 private first-answer capture merged; real paired scores pending

**Merge verified on main:** [PR #1413](https://github.com/ienam-smarthome/HomeBrainOS/pull/1413)
merged exact checked head `b15626708982514b8150275c876d1174b68b51f5`
with merge commit `878783be6d56d656b72a8d8e1f81c9f11d9065da`.
All three required workflows passed (Release assurance, Validate HomeBrain OS,
Answer Quality scorecard integrity), including **6,444 Python tests passed,
2 warnings**; add-on container smoke and metadata validation green.
23 new Q2 Python tests are included in this total. This is a
**non-runtime offline-evaluation tool**, not an installed release;
add-on version remains **0.18.404**.

**Delivered:** `scripts/answer_quality_q2_private_capture.py` can
privately save the *actual first model prose* and exact-answer
SHA-bound run metadata on 1–4 pre-existing fixed source packets
for an explicitly invoked Ollama local or direct Ollama Cloud A/B.
It keeps all response plaintext outside the public repo,
requires a fresh private output directory, refuses public CI
inference and provider redirects, disallows model-tool calls,
uses no retries, checks installed local model tags, and explicitly
refuses local-tagged `cloud` models bypassing cloud consent.
Direct Ollama Cloud requires a separate explicit cost acknowledgement
and environment API key; **no Cloud/Gemma inference was made during
development or CI**. Prepopulated but **ungraded/null** SHA-matched
review rows are created for human source review and rejected by
the scorecard until evaluated. See
[Q2 private capture protocol](ANSWER-QUALITY-Q2-PRIVATE-FIRST-ANSWER-CAPTURE-20261104.md).

**Measurement boundary:** CI reports code contracts, not actual
Gemma-vs-alternative quality. The previous Q1 MQTT and hub-health
installed observations stand; **0 newly reviewed actual model A/B pairs**
in this release, factual grounding/causal calibration/Claude parity
and p50/p95 still `not_measured`. No Hubitat, HA, router, rule or
device mutation. Next real Q2 action is an **explicitly consented
actual first-response capture** against frozen evidence (local-only
if avoiding possible Cloud charges), followed by **independent
private answer/source review** and the existing
`scripts/answer_quality_paired_reviews.py`. No unmeasured
reasoning improvement claim.

---

## 2026-11-04 — Q2 source-verified first-answer A/B: private capture workflow candidate

**Next step after Q1:** Existing Q2 no-cloud GitHub runner recorded true
small-local-model first-answer response timings and SHA digests but
deliberately discarded raw replies. That cannot support human source
review of causal calibration, first-answer usefulness or naturalness.
Existing `answer_quality_paired_reviews.py` requires answer-SHA-bound
private human reviews, not merely completion counters.

**Proposed Q2 capability:** `scripts/answer_quality_q2_private_capture.py`
provides an explicit local run on 1–4 fixed synthetic/anonymised source
packets (default four across causal issuer, heating, MQTT and rules).
Each model receives exactly the same rendered prompt, one request per
arm with no retry, fixed requested settings and no MCP tools. Private
raw answers, SHA-256 metadata, and **unfilled** (null-grade) answer-linked
human review forms are written only to a new directory outside this
repository. Local loopback/Ollama model inventory is supported; the
official Ollama Cloud Gemma endpoint requires separate `--run`,
`--ack-cloud-usage` and an environment API key. No cloud call or model
response is executed by CI. There is no unconsented billing, Hubitat/HA
write, production runtime code or add-on version change. Mocked tests
verify source equality, exact hashes, false-score rejection, tool-free
requests, explicit cost acknowledgement, private output and failures.

**Measurement:** This implementation is offline evaluation
infrastructure only. First-model reasoning quality, Gemma-versus-
alternative human-reviewed paired results, Claude comparison,
production publisher effect and p50/p95 **NOT MEASURED** until real
model replies and actual human source reviews exist. Previous Q1
observations stand unchanged.

**Acceptance/continuation:** Verify full exact-head CI and
documentation; do not merge if gate red. Then perform an explicitly
approved private, actual first-answer capture on installed/local
model transports and compare manually reviewed identical packets
with existing `scripts/answer_quality_paired_reviews.py`. Do not
extrapolate from synthetic tests or tiny local models to Gemma.
[Implementation and limits](ANSWER-QUALITY-Q2-PRIVATE-FIRST-ANSWER-CAPTURE-20261104.md).

---

## 2026-11-04 — Q1 v0.18.404 broad hub health: live snapshot good, alert coverage partial

The exact registered read-only `broad_hub_health` question
(`What is the hub health status?`) returned `success` with
**9.376s wall-time**, **2** free Gemma model rounds, **1**
read-only `homebrain_hub_info_snapshot(scope=full)` call,
**3.019s provider** and **6.021s local tool**. Driver-source
values supported CPU 0.67 / 16.75% reported CPU, free RAM
767.41 MB, database 163 MB, uptime 22h39m22s,
firmware installed/available 2.5.3.117, Zigbee enabled
healthy=true, Z-Wave disabled, Matter online. No temperature
value was present; published answer withheld it and avoided
claiming complete health or no alerts.

**Partial acceptance only**: one scalar snapshot, not an alert
inventory or historical-log freshness check; full `live
metrics and alerts` source coverage **not established**. Source
timestamps, external firmware freshness and physical hub
health unverified. `typed_status_source_claim_repairs=4`,
`model_delivery_verified=false`, `first_attempt_verified=false`,
`deployed_build_sha_verified=false`. No independent first-draft
accuracy score. Driver diagnostics include 2 refresh commands
and 1 poll read within read-classified snapshot. Routine
under-15s target met on this one observation, **not p50/p95**.

Next: move toward **Q2 frozen same-evidence model reasoning A/B**;
preserve the generic hub-alert source coverage gap for later
cross-case Q1/Q3 investigation, with no hub-specific wording patch.
[Detailed review](ANSWER-QUALITY-Q1-HUB-HEALTH-V404-LIVE-20261104.md).

---

## 2026-11-04 — Q1 v0.18.404 installed MQTT/health acceptance: measured improvement

**Live installed paired case:** The unchanged read-only `device_mqtt_conflict`
question was run once on add-on version **0.18.404**. Published answer was
useful and appropriately `unresolved`: healthStatus offline vs MQTT connected
are different reported layers, clocks disagree (**567.9h** from lastSeen vs
**45.1h** reported data age), and physical device status, broker packets,
installed driver/watchdog method and outage cause were **not verified**.
The 24h bounded history returned 13 state/attribute events (including
disconnected/reconnected MQTT reports) and 0 commands. This is not a
verified history of genuine endpoint packets.

**Measured single-request improvement:** v0.18.404 wall **29.023s**,
provider **21.780s**, **6** free Gemma rounds, **7** read-only tool calls,
versus installed v0.18.403 **42.635s**, provider **35.241s**,
**8** rounds and **13** calls. Difference **-13.612s (-31.9%)**,
-2 rounds, -6 calls. v0.18.402 was 36.507s / 6 rounds / 8 calls.
Not a measured latency distribution or proof of causality.

**Corrected publication, not proven model-first accuracy:**
`telemetry_post_read_sufficiency_stop=1`; new bounded evidence gate used.
`telemetry_source_claim_repairs=2` (driver and clock).
Publication still replaced model-authored text:
`publicationBoundaryShadow.replacementPerformed=true`,
`publishedIsFirstModelDraft=false`; model-delivery/first-attempt/build-SHA
attestation all false. Source-class checks complete but
`evidenceComplete=false`, `rootCauseVerified=false`, no independent
broker packets, driver behaviour or physical communication verified.
A legitimate device config read occurred; no device-ID-as-app-ID
Groovy lookup observed. No Hubitat/HA/router/device writes.

**Decision:** Accept this single published-answer and wall-time
regression; do **not** score raw-model correctness or p50/p95 and do
not patch/repeat this same MQTT device. Next frozen different-domain
Q1 read-only case is `broad_hub_health`: `What is the hub health status?`
Get one full natural answer + Technical JSON, review current live
health versus unsupported root cause, then progress to Q2 same-evidence
model comparison. [Details](ANSWER-QUALITY-Q1-TELEMETRY-V404-LIVE-ACCEPTANCE-20261104.md).

---

## 2026-11-04 — Q1 MQTT/health v0.18.403 published grounding improved; saturation v0.18.404 candidate

**Paired live installed observation:** The exact frozen read-only
`device_mqtt_conflict` question was rerun on 0.18.403.
Published answer: correctly distinguishes saved `healthStatus=offline`
from `mqttStatus=connected`, refuses physical/driver-watchdog root
cause proof, and reports `lastSeen` metadata **566.8h** versus
`dataAgeSeconds` **45.1h**, `sourcesAgree=false`.
Outcome appropriately `unresolved`. Publication applied
`telemetry_source_claim_repairs=2` (driver method + physical
assertions). The underlying model's first no-tools draft was
**not** published unchanged; `modelFirstRejection` says
`model-draft-provenance-changed`, and
`publicationBoundaryShadow.replacementPerformed=true`.
Do not score it as independently grounded raw-model reasoning.

**Performance regression:** 0.18.402 paired response 36.507s,
6 free model rounds, 8 tool calls, provider 29.747s, versus
0.18.403 42.635s, 8 rounds, 13 tool calls, provider
35.241s. Difference **+6.128s**, 2 extra rounds and 5
extra calls; two live samples are not a controlled latency
distribution or proof of which code caused the difference.
The v403 trace includes source/tool discovery and
`homebrain_read_groovy_source(appId=7103)` after target
device **7103** was already independently verified; this
is a device ID, not an app instance identity. Installed
source proof returned zero verified characters. A failed
`hub_get_app_config(appId=7103)` and device-dependency
reads add no independent proof of installed driver code.

**Q1 general defect / candidate 0.18.404:** Source-saturated
status/history/logs plus independently contradictory
`lastSeen` and data-age clocks provide a bounded answer
to a single device's `offline` vs MQTT `connected` contrast
without needing unsupported physical/driver investigation.
Add general stop after independently checked status,
bounded history, scoped logs and actual clock mismatch;
preserve uncertainty, cross-device and write protection.
An optional failed tool in a round must not erase the
necessary successful read evidence. Add a verified-device
vs Groovy-app instance identity admission guard to prevent
device IDs being passed as app IDs absent an actual
typed device-dependent app link. No extra reads/model
rounds; no alteration to actual driver/Hubitat/HA/router.
[Source review](ANSWER-QUALITY-Q1-TELEMETRY-STOP-20261104.md).

**After-live quality/latency unmeasured.** Synthetic CI
is not physical or first-draft model verification.
**v0.18.404 code merged / all required CI green:**
[PR #1409](https://github.com/ienam-smarthome/HomeBrainOS/pull/1409)
passed all four workflows at exact tested head
`b4047c136508c454a1898209e2557c3e739c4e9d`:
**6,421 Python tests passed (2 warnings)**, release assurance,
container smoke, Hubitat MCP AI, validation and Answer Quality
integrity. Merge commit
`f796b83fa6e8f5fbe1419d86d144f5b2d25e56c5`.
Addon version **0.18.404** and both the source saturation
rule and app/device identity guard are verified on main.
**No installed after-response or actual latency improvement
has been measured yet**. CI green is not a first-draft
reasoning score, p95 measurement or a proof of physical
MQTT responsiveness.
After installing the release, run the exact frozen
read-only question *once* as paired acceptance, inspect
stop counters, answer and Technical JSON, then stop
repeating the same device case and continue another
Q1 domain toward same-evidence Q2 model comparisons.

---
## 2026-11-04 — Q1 MQTT/health reasoning source-scope failure; v0.18.403 candidate

**Live registered read-only case:** User submitted exactly
`Why does Bedroom 3 Mesh show MQTT connected when its health is offline?`
on installed HomeBrainOS **0.18.402**. Gemma returned an
**unresolved** answer in **36,507 ms** (provider 29,747ms,
6 free-model rounds, 8 read-only tool calls). It correctly
recognised `healthStatus=offline` and `mqttStatus=connected`
as distinct reported fields, and withheld a definite external
power/WiFi/broker physical root cause at the end.

**Core factual overclaims:** The published narrative nevertheless
declared the device physically offline, `mqttStatus` definitively
cached owing to a specific missing disconnect-message mechanism,
and `healthStatus` a live watchdog calculation. It interpreted
stored Oct12 `lastSeen` as definitive physical last contact
and reported `dataAgeSeconds` (~45.1h) as actual last telemetry.
Typed host telemetry-clock analysis instead reports **566.1h vs
45.1h, `sourcesAgree=false`, physical telemetry not proven**.
History included positive MQTT disconnect/reconnect events
(Nov 3), contradicting the blanket no-disconnect assertion.
Source coverage itself says `verifiedInstalledDriverBehaviour=false`,
`driverMethodBehaviourVerified=false`, no independently retained
broker packets, `rootCauseVerified=false` and
`questionResolved=false`. Hub logs were queried, but the
technical receipt did not retain typed watchdog executions or
verified implementation. No live actions were performed.

**General candidate 0.18.403:** New model-independent
read-only telemetry publication gate consumes existing
source-identity, attested clock consistency, driver-method
coverage and positive event receipts. It corrects unsupported
categorical physical/driver/last-packet/no-disconnect assertions
while keeping qualified hypotheses and useful model-authored
explanations. No new device-specific rule, MCP call, model round,
configuration or device change. Generic synthetic tests cover
other device IDs and malformed/mismatched evidence.
[Source review](ANSWER-QUALITY-Q1-TELEMETRY-SOURCE-BOUNDARY-20261104.md).

**Before measurement**: 36.507s/6 rounds/8 calls, substantive
Q1 causal-calibration failure. **After live result not measured**.
No independent model first-attempt accuracy, p50/p95, source-code
watchdog verification or Claude parity claim is supported.
Do not manufacture a resolved cause from a coverage-unresolved
result. **Verified v0.18.403 merge:** [PR #1407](https://github.com/ienam-smarthome/HomeBrainOS/pull/1407)
passed all four required workflows on exact tested head
`3e6eeda36fa78be3bcce8cbd5f59458585ba513c`: **6,410
Python tests passed (2 warnings)**, container smoke, metadata,
Hubitat MCP AI tests, validation and Answer Quality integrity.
Merged `f9414b16f1d87a942af466488e9bbc318d3a2c0f`.
Version **0.18.403** and the new source boundary were verified
on `main`. **Installed post-update answer quality and latency
remain NOT MEASURED.** This is a code-level claim-scope
correction, not proof of restored physical MQTT connectivity
or of independently grounded first-draft reasoning.

**Next live read-only acceptance:** Repeat the frozen question
after install only if needed for a paired same-question regression;
review clock conflict in final prose, no unverified driver
methods, and no physical-status overclaim. Then continue Q1
on a different source/domain without repeated device-specific
patching. Q2 requires same-evidence model A/B, not synthetic
CI success alone.

---
## 2026-11-04 — Q1 v0.18.402 installed active-light aggregate coverage VERIFIED

**Same registered read-only question, paired regression (not a new
independent first-attempt score):** In a fresh HomeBrain topic, user
submitted exactly `Which lights are currently on?` on installed
0.18.402. The API prompt digest matched the earlier 0.18.401
`all_lights_on` case (SHA256
`b355a6ac4b1dd90a2ed2d06ebff5b5880d80eabe14e9e5afe5dccc3410415272`).
The natural answer was `2 lights are on: Bedroom 2 Light and Toilet Light.`
These are the names supplied by the model, **not independently attested
per-device identities in the sanitised Technical JSON**.

**Source-completeness observation:** One successful read of
`hubitat://context` returned **211 device records**. The
`homebrain_active_lights` deterministic source returned and
published typed `aggregateState` counts: `category=lights`,
`onCount=2`, `candidateCount=13`, `unknownStateCount=0`,
`totalScanned=211`, `scope=whole-home`, `scopeVerified=true`,
`inventoryComplete=true`, `stateCoverageComplete=true`.
The sanitised receipt now makes the on-count and recorded-state
completeness independently inspectable without leaking the full
household device list. It establishes **two ON among 13 recognised
lighting candidates under HomeBrain's classification rules**,
not whether every physical fixture was discovered, that the
named two device labels were correct, or actual light emission.
The source snapshot differs in time from the earlier v0.18.401
zero-ON report; those differing ON counts are not an inherent
contradiction, since lighting can change between observations.

**Performance:** v0.18.401 wall **4,054ms**, provider 2,668ms,
2 model rounds, 2 tool calls, no typed count receipts; v0.18.402
wall **4,109ms**, provider 2,499ms, 2 rounds, 2 calls, newly
auditable source count/coverage. The 55ms (1.36%) wall increase
across two separate requests is not meaningful evidence of a
systematic slowdown, and both meet the 15s routine-read target.
No `aggregate_zero_claim_repairs` were recorded; the model's
positive count matches the aggregate receipt. Zero repairs is
not independently authenticated proof of first-draft quality.

**Q1 acceptance:** Structural aggregate count and coverage
instrumentation PASSED live acceptance, with no extra MCP or
model calls. Individual name-to-source attribution and physical
state verification remain OUTSIDE the presented receipt. Do
not count this same-prompt repeat toward the first-attempt
accuracy denominator; `first_attempt_verified=false`,
`model_delivery_verified=false`, and
`deployed_build_sha_verified=false`. Q1 population accuracy,
cross-model parity, repeated-run p50/p95: NOT MEASURED.
No new light-specific runtime patch is justified here.

**Next registered, different-domain Q1 test:** In a NEW
HomeBrain topic, submit EXACT unchanged legacy read-only case
`device_mqtt_conflict`:
`Why does Bedroom 3 Mesh show MQTT connected when its health is offline?`
Provide the complete first natural-language answer and
Technical JSON. Inspect broker session vs fresh endpoint
telemetry, recent source timing, stale metadata and whether
the answer invents a physical failure or cause. No device
commands or writes are authorised. Continue Q1 independent
source review before Q2 same-evidence model comparisons.

---
## 2026-11-04 — Q1 lighting inventory: zero-count source-completeness gap; v0.18.402 candidate

**Observed installed 0.18.401:** Registered read-only case
`all_lights_on`, exact question `Which lights are currently on?`.
Gemma output `No lights are currently on.` in **4,054ms**
(provider 2,668ms, MCP HTTP 1,332ms), 2 model rounds, 2
tool calls. The bulk `hubitat://context` read returned **211**
device records; `homebrain_active_lights` executed successfully,
but the Technical JSON receipt exposed only `lights/count/complete`
FIELD NAMES, not actual active-light count or completeness values.
Thus the supplied evidence does not independently verify that
zero is correct, nor prove that the answer was wrong. No physical
light states were independently observed for this question.

**Generic root cause:** Complete inventory IDs do not guarantee
that every eligible light/switch emitted a usable `switch` value.
The previous local aggregates mapped only reported ON devices
and set `complete` from resolved room scope. An otherwise
complete context could silently omit the state of an eligible
device, and tool receipts prevented external audit of the
aggregate's actual ON count. A nonzero retained dimmer level
while OFF does not mean the light is ON.

**Candidate 0.18.402:** Shared source-derived ON/OFF/unknown
coverage for light and non-light switch aggregates, with
room-verified filtering and label-only light-sensor protection.
Retain the fast single bulk context; expose bounded, privacy-
safe typed count/coverage receipts. A final publication check
accepts zero-active conclusions only when actual ON count is
zero, eligible candidates exist, inventory and switch coverage
are verified; otherwise qualify the statement without
fabricating device states. This is a general coverage/evidence
mechanism, not an incident-specific rewrite or new model round.
[Source review](ANSWER-QUALITY-Q1-AGGREGATE-COVERAGE-20261104.md).

**Before time:** 4.054s single observed response meets the
15s routine-status threshold, but accuracy and full source
scope are not independently established by the provided
receipt. Formal first-attempt and model-delivery verification
flags false. **After deployment Q1 live result NOT MEASURED.**

**Acceptance:** After all CI green and installing v0.18.402,
repeat the exact registered question in a new topic, send
the full answer and Technical JSON. Inspect typed
`aggregateState.onCount`, `candidateCount`, `unknownStateCount`,
`inventoryComplete`, `stateCoverageComplete` and source scope.
Then continue independent cross-domain Q1 rather than
claiming a population first-attempt score from repeated cases.

---
## 2026-11-04 — Q1 Hub Health v0.18.401 live regression: FINAL grounding PASSED; draft still unverified

**New same-question installed test (not a new first attempt):** The user
repeated the exact registered read-only `broad_hub_health` question
`What is the hub health status?` on **HomeBrainOS 0.18.401**.
The API's normalized-prompt SHA-256 matched the earlier 0.18.400
request (`b586998f15c01644355754722ae36cce273a5026d2c436046e6a441b05ebf23c`).
The API still reports `first_attempt_verified=false`,
`model_delivery_verified=false`, and `deployed_build_sha_verified=false`;
the exact deployed source SHA and independent draft correctness remain
unattested. These flags and one repeated test do **not** establish
first-attempt population accuracy.

**Actual typed-source review:** One successful scoped, nonmutating
`homebrain_hub_info_snapshot` with 18 reported fields supported:
`cpu_5_min=0.41`, `cpu_percent=10.25`, `free_memory=792.21 MB`,
`database_size=173 MB`, uptime `0d:19h:8m:47s`, installed and
available firmware both `2.5.3.117`, Zigbee `enabled` with
`healthy=true`, Z-Wave `disabled`, and Matter `online`.
The source included `temperature_unit=°C` but no numeric
`temperature` field; it could not verify complete alert absence,
external firmware freshness or physical radio connectivity.

**Published answer passed source-field grounding:** The output
reported the supported scalars, explicitly said temperature was not
reported, qualified global health/alert absence, described firmware
as matching source-reported versions without independently verified
external freshness, and called Zigbee enabled (healthy=true) instead
of unqualified online. No unsupported temperature or global-health
claim remained in the final message. The model's natural narrative
was still somewhat mechanical due to correction text.

**Important interpretation:**
`metrics.counters.typed_status_source_claim_repairs=4` proves
the publication guard applied FOUR source-claim corrections.
It does **not** prove the underlying Gemma draft was already
grounded. `evidence_validation.contradictions_corrected=[]` remains
empty; this is a separate observation channel, not proof that
zero source repairs happened. An independently attested first
draft, paired model evidence and representative Q1 sample set
are still needed before an accuracy/parity claim.

**Measured single-test performance:** v0.18.400 wall **11,139ms**
(provider 4,896ms, local tool 5,953ms, 2 rounds, 1 call) versus
v0.18.401 wall **10,422ms** (provider 3,457ms, local tool
6,568ms, aggregate MCP HTTP 6,867ms, 2 rounds, 1 call).
This is **717ms (6.4%)** faster in two differing live observations,
not a controlled benchmark or p50/p95. The later 10.4s answer
meets the single routine-status 15s target. No new Hubitat, HA,
router, device, or Rule Machine action was performed during
this documentation work.

**Next unchanged Q1 cross-domain live prompt:** Frozen legacy
read-only case `all_lights_on`: `Which lights are currently on?`
Open a NEW HomeBrain topic and submit exactly that question.
Return the first complete natural-language answer and Technical JSON.
Review inventory/source completeness, inclusion/exclusion of dimmers
with saved nonzero levels while OFF, room/device identity, telemetry
freshness, claim confidence, answer clarity, runtime, and tool
efficiency. No devices may be changed and no write confirmation
should be approved. Continue other Q1 domains before Q2
same-evidence model comparison. **No further incident-specific
Hub Info patches are justified by this successful final answer.**

---
## 2026-11-04 — Q1 typed-source grounding: Hub health → cross-domain correction

**New frozen Q1 domain observation:** Installed 0.18.400 responded
to `What is the hub health status?` in 11,139ms with 2 Gemma rounds
and 1 successful Hub Information Driver typed snapshot. The answer
accurately reported available 5-minute CPU 0.78 / 19.5%, memory
756.39 MB, DB 175 MB, uptime 18h33m54s and source-reported
system statuses, but asserted temperature **42.5°C** with no value
in `reported` (only a °C unit). It also claimed a complete healthy
hub, no alerts and externally up-to-date firmware beyond the
typed source's completeness/freshness. No packet-level endpoint
or independent alert check exists in that receipt.

**Later user screenshot of Hub Info C8 Pro (device 1089):** UI showed
changed CPU 1.36/34.0%, memory 782.07 MB and DB 177 MB.
These are a separate later observation, not a contradiction of
the earlier API snapshot; the screenshot does not show the complete
attribute inventory or prove a timestamp for every field.

**General development candidate 0.18.401:** One shared final
typed-source guard reconciles precise status claims against
reported scalar values and scoped device identity across Hub Info,
light/device states, power, humidity, battery and other supported
status measurements. Source unit metadata does not prove a value;
conflicting same-ID snapshots are not combined. Unsupported
global alert/health and external firmware claims are qualified.
No new model rounds, MCP reads or mutation permissions. Pure
synthetic tests assess field/identity/format/absence boundaries.
**Verified merge and tests:** [PR #1402](https://github.com/ienam-smarthome/HomeBrainOS/pull/1402) passed all four required workflows on exact tested head `03a5d68a914eb4a94b64a65d2c55fc8524034cb3`: **6,385 Python tests passed (2 warnings)**, metadata, add-on container smoke, validation and Answer Quality integrity. Merged to `main` as `e6c5130903441da5efc7fcfe39daf50ea649d9c8`. Add-on version `0.18.401` verified on main. **Installed after-response and latency remain unmeasured.**
[Detailed source review](ANSWER-QUALITY-Q1-TYPED-REPORTS-20261104.md).

**Q1 paired snapshot regression measured:** v0.18.399 two-light
question 19.409s, 6 model rounds, 7 tool calls, unnecessary
one-sided history → v0.18.400 same-question repeat 8.227s,
3 rounds, 4 calls, no history, independently correct current
device states. Reported Hallway ON/50 and Livingroom OFF/retained
60 in the later read; state changes over time are not contradictions.
This is a single repeated test, not a new first-attempt score.

**Next read-only acceptance after deployment:** Submit the exact
registered hub-health question again and provide the natural
answer and complete Technical JSON. Review field coverage,
uncertainty and natural response. A repeat is not a new first
attempt; continue independent cross-domain Q1 before Q2.

---
## 2026-11-04 — Q1 first read-only multi-device state sample; 0.18.400 candidate

**Observed installed v0.18.399 (one user-supplied first-received response):**
The frozen `multi_device_named` read-only prompt and API-bound SHA-256
were supplied privately along with the full natural answer and technical
trace. Two separate exact device resolution receipts established matching
Hubitat reported `switch=off` and retained `level=50` / `level=60` for
the two named lights. The answer accurately relayed those reported
values but called dimmer levels 'brightness' while lights were off.

**Evidence/coverage defect:** The model unnecessarily requested a bounded
24-hour history for only the first light; five reported switch ON→OFF
intervals summed to 465 seconds, with history source integrity marked
unverified and observed event rows truncated. The answer added
unrequested activity and an automation-issued command narrative which
could not establish the upstream trigger for all five intervals.
The host labelled `metrics.outcome=success` but separately reported
`investigation_coverage.questionResolved=false` and
`sourceScopeComplete=false` owing to missing *second-light history*,
even though the original question asked for **current states**, not
past activity. This is inaccurate objective classification and misleading
coverage, not proof the two current state values were wrong.

**Observed performance:** 19,409 ms wall, 18,143 ms agent,
14,568 ms provider, 3,357 ms MCP HTTP, six Gemma free rounds
and seven tool calls; the single observed status request exceeded
the 15-second charter target. These are one execution's observations,
not a median/p95 or a controlled before/after result. Published response
`success=true` is a transport success; model delivery, independently
attested deployed SHA and `first_attempt_verified` are all **false**.
Formal independently source-reviewed first-attempt score remains
**NOT MEASURED**; no Claude comparison has occurred.

**General candidate v0.18.400:** Shared `investigation_policy` now treats
comparisons of current status, switch state, saved levels and brightness
as *snapshots*, not historical investigations just because they contain
the word `compare`. Explicit events, timestamps, trends, past states,
causal and unusual-behaviour comparisons keep their history requirements.
Generic status prompt guidance discourages unrequested event reads and
causal overclaims without taking over the model's answer. Synthetic
negative tests include missing second-target historical receipts and
actual historical comparisons. No write/tool authorization, Cudy driver,
Hubitat, HA or router changes. [Q1 source review and acceptance](ANSWER-QUALITY-Q1-SNAPSHOT-COMPARISON-20261104.md).
**Verified green merge:** [PR #1400](https://github.com/ienam-smarthome/HomeBrainOS/pull/1400)
tested at exact head `ab74c7c3008292dee993d4b51056b03a23c0b5ad`,
passed all **four** required workflow runs (Release assurance,
Hubitat MCP AI tests, Validate HomeBrain OS and Answer Quality integrity),
including **6,363 passed, 2 warnings**, add-on container smoke, metadata
and validation. Merged `30c9dffb22aa2f118c6bc1fa7f7d8b3541dc3d26`,
with `hubitat-mcp-ai/config.yaml` on main verified as **0.18.400**.
**Installed same-question after-response and actual improvement remain
NOT MEASURED.** Tests show code-level distinction and safety only,
not that Gemma's final natural language will improve in the field.

**Next user acceptance after green merge/install:** Repeat exactly
`Compare the states of Hallway Light 1 and Livingroom Light 2.` in
a new HomeBrain topic, provide first full natural answer and Technical
JSON. Check whether the model avoids unsolicited history, reads both
current states, reports saved levels with correct off-state semantics,
does not fabricate an automation cause, and falls under 15 seconds.
Since this is a repeated prompt, it is **not** a new first-attempt
benchmark. Continue cross-domain Q1 evidence before Q2 same-packet
Gemma-vs-alternative reasoning. Roll back if actual historical
comparisons lose required source coverage.

---
## 2026-11-04 — timed Internet field validation DONE; permanent Q1 Answer Quality resumed

**User-observed functional acceptance (not a Q1 answer-quality score):** The
installed HomeBrainOS v0.18.398 and hub-resident Cudy driver successfully
scheduled and executed a 2-minute Internet block for the first media device.
The driver reported blocking just after the deadline; the user confirmed
they manually restored Internet access. With v0.18.399, the separate media
device also armed a 2-minute timer and reported **timer reached** and
**Internet BLOCKED** at 11:45:17 GMT (about 0.25s after the local target).
The driver later reported **Internet ALLOWED** at 11:46:26 GMT; the issuer
of that subsequent allowance has **not** been independently established.
Hubitat logs reported MAC blocking and conntrack flushing; no independent
packet-level connectivity probe was supplied. No Hubitat/HA/router writes
were made by the repository work.

**Performance — verified single two-device comparison, not a population
distribution:** The earlier v0.18.398 initial timer proposal was
**38.160s** (37.951s MCP HTTP); the v0.18.399 first proposal was
**1.541s** (1.534s MCP HTTP; timed-internet summary preflight 1.056s).
That is a ~25x / ~96% difference between two **different** media devices,
not a controlled identical-device throughput trial or a first-answer
accuracy result. Confirmed driver command/readback took roughly 1.8s
on the TV example and 1.6s on the other device. Engineering PRs
[#1396](https://github.com/ienam-smarthome/HomeBrainOS/pull/1396)
(0.18.398, merged `23196101`) and
[#1397](https://github.com/ienam-smarthome/HomeBrainOS/pull/1397)
(0.18.399, merged `c8aec3f9`) passed the blocking release gates.
Live multi-device batch cancellation and missed-hub-reboot jobs remain
unverified; do not infer them from two successful single-device timers.

**Original user direction restored:** Return to the permanent Answer
Quality Q1→Q2→Q3→Q4 roadmap documented in
[ANSWER-QUALITY-CHARTER.md](ANSWER-QUALITY-CHARTER.md). Do not continue
incident-specific timer patches. Maintained add-on version is
**0.18.399**. Current 53 registered evaluation cases = 13 legacy
tasks + 40 curated synthetic offline source packets. The official
independently reviewed first-attempt accuracy/grounding denominator is
still **0 (NOT MEASURED)**. A timed-block success or CI count must not
be counted as answer correctness or Claude parity.

**Current Q1 milestone:** Add a privacy-safe one-response intake utility
`scripts/answer_quality_live_sample.py`, which binds the
source response to the **exact registered API prompt digest**, preserves
only source-execution/timing/outcome metadata, and always leaves human
source grading and first-attempt certification **not measured**.
See [Q1 intake procedure](ANSWER-QUALITY-Q1-LIVE-SAMPLE-INTAKE.md).
**Verified merged Q1 tooling:** [PR #1398](https://github.com/ienam-smarthome/HomeBrainOS/pull/1398)
passed all required workflows on exact head
`13405be2777df55d22deed5041a5d3e753376970`, including **6,344
Python tests passed (2 warnings)**, metadata, add-on smoke, Answer Quality
integrity and validation. Merged to `main` as
`852703ac4f35cdcbeead6a0688f8e583fa6bbb42`. This is an **offline
evaluation utility** only, not a deployed answer-quality improvement or
measured first-attempt score. No add-on runtime change, no further timer
patch, no live Hubitat/HA/router actions and **no version bump**.
Maintained add-on source remains **0.18.399**.

**Next user-supplied acceptance (one read-only first response):** In a
fresh HomeBrain topic, submit exactly the unchanged registered
`multi_device_named` prompt:
`Compare the states of Hallway Light 1 and Livingroom Light 2.`
Return the first natural-language answer **and complete Technical JSON**
privately. Do not change anything. Independently review source identity,
individual current switch and level reads, staleness, tool outcomes and
whether the answer says more than its receipts support. This is a new Q1
observational sample, NOT an authenticated certified first attempt while
the API sets `first_attempt_verified=false`.
Then continue Q1 measured cross-domain evidence before Q2 same-source
Gemma versus alternative model comparison. Roll back the evaluation-only
intake PR if it leaks sensitive source details or mistakes transport
success for grounded answer quality.

---

## 2026-11-04 — v0.18.397 native MCP installed-version fix MERGED

**User-observed baseline:** On installed HomeBrain 0.18.396, the request `Block TV after 30 mins` entered deterministic scheduled-write path and returned unresolved in **121 ms**, with one verified `hub_get_tool_guide(set_rule_reference)` read, zero other reads and no write. Message: `native_oneshot_date_field_unverified` because cached MCP initialize did not attest installed Rule Server **>=5.1.6**. Earlier Hubitat read reported **5.1.5**, but exact current version was **not established by this failed request**. Upstream [#575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) closed with new date-field support for >=5.1.6. The user wants the original one-shot workflow; **the cumulative allowance app is NOT required**. The daily one-time cleanup was shown enabled for 07:00 (last run 4 Nov, zero deletes/failures). It only removes expired `HB one-shot |`-named rules; user-created test rule 4285 stays untouched.

**Merged 0.18.397 general fix:** [PR #1394](https://github.com/ienam-smarthome/HomeBrainOS/pull/1394) passed **7/7 CI** including **6,287 Python tests** (2 warnings) on head `56b1dbc55305103c21273b534f95e5df3b8baac5`, then merged as `b38200670a137e6fb65b37448eed8afc4c899b1c`. Source code version in `hubitat-mcp-ai/config.yaml` is **0.18.397**. Underlying upstream server exposes the exact version from `initialize.serverInfo` and read-only `hub_get_info.mcpServerVersion`. The deterministic rule compiler now reads current hub info only when cached initialize identity is missing or older, gives the actual version and HPM upgrade guidance, and when current server claims >=5.1.6 attempts to reconcile with a refreshed initialize identity before allowing a native dated create. Source errors/mismatches fail closed, no guessed legacy fallback. Native-document metric is no longer labelled unsupported merely because the guide advertises native creation. Regression tests include genuine old-version refusal, stale-identity recovery, the user's exact "Block TV after 30 mins" no-write behavior, and confirmation replay gate. **Engineering CI and GitHub merge VERIFIED; real post-install first-attempt resolution and scheduled firing: NOT MEASURED**; a new HomeBrain release alone cannot upgrade an old MCP Rule Server. No Hubitat/HA/router writes. Next: user updates HomeBrain to v0.18.397, then retries the exact prompt. The new read-only `hub_get_info` version evidence will reveal whether Hubitat MCP needs HPM upgrade to >=5.1.6; after any upgrade reconnect HomeBrain. User confirmation, native rule readback, a scheduled job and later execution/Internet effect still require independent verification. The original 07:00 one-time cleanup remains enabled based on user screenshot; no live Hubitat/HA/router changes were made by this PR.


## 2026-11-04 — native Rule Machine summary scalar compatibility, v0.18.396 candidate

**Observed installed 0.18.395 first attempt, real model:** User-supplied read-only question about test rule ID **4285** returned `named-rule-read` in **730 ms**, with matching source rule identity and three ordered action methods. However it reported 69/71 settings redacted/unsupported and failed to show the known typed 08:00, Switch OFF, 15-minute wait, Switch ON fields. The same user's v0.18.394 native field-by-field read reported 6/71 unsupported and included those typed settings. This is an **observed first-answer quality failure**, not a completed scheduling or rule execution claim. The user expressly said this is a **test rule**; no live rule must be modified.

**General fix hypothesis:** The v0.18.395 renderer's duplicate validation rejected native setting rows with optional `device_ids=null` that the existing privacy-safe `_simple_setting` reader accepted. Hubitat forms can represent typed `bool` and `number` values as strict strings. v0.18.396 candidate reuses that canonical sanitizer, accepts only typed exact `true`/`false` and bounded typed integer-string waits; ambiguous values remain unknown. Generic tests cover unrelated Switch targets, 71 settings with 6 redactions, malformed values and privacy. No additional MCP/tool/model round and **no Hubitat/HA/router mutations**. Full CI/PR/merge and **post-install real first-answer comparison NOT MEASURED** as of this entry. Roll back if source attribution/privacy regresses. Next acceptance: repeat the same read-only named-rule question after the release and compare actual first-answer fields/latency with this baseline.


## 2026-11-04 — v0.18.395 named Rule Machine read answer quality candidate

**Observed installed 0.18.394:** The user confirmed **Rule Machine ID 4285 `One-off block TV` is a test rule**. Their first HomeBrain answer correctly routed to `named-rule-read` and used `hub_list_rules` + `hub_set_rule(operation=read)` in **548 ms**, but printed **71 internal native settings (6 redacted/unsupported)** instead of resolving the asked sequence in natural language. The stored settings indicate `atTime1=08:00`, action IDs `1=getOnOffSwitch` (typed `onOff.1=false`, device ID 6923), `3=getWaitEvents` (`delayMin.3=15`), and `4=getOnOffSwitch` (`onOff.4=true`, device ID 6923). The date flag was empty; no dated one-time trigger can be established merely from this test rule's name. No evidence of actual scheduling, firing, or network reachability was supplied. **The test rule must not be modified or used as production.**

**Candidate 0.18.395:** A generic source-scoped, redaction-safe formatter maps native action IDs to typed saved settings and summarises trigger time plus ON/OFF/Wait ordered configuration. It explicitly distinguishes dated one-time fields, undated times, conditional action graphs, unavailable device targets, unsupported action semantics, and actual run state. The existing explicit raw native-section reader remains untouched for technical diagnostics; same two source reads and no extra AI rounds. Synthetic regression includes a 71-setting / 6-redacted packet and unrelated switch IDs, *not* hardcoded Google TV behavior. CI and merge to be verified. **First-attempt installed answer benefit, model quality and future scheduled execution remain NOT MEASURED.** No live Hubitat/HA/router changes. Roll back if the formatter fabricates execution or suppresses source errors.


## 2026-11-04 — v0.18.393 exact named-rule read and v0.18.394 native one-time scheduling merged

**Merged:** [PR #1389](https://github.com/ienam-smarthome/HomeBrainOS/pull/1389) passed 6/6 CI checks at head `703953c5a7e5e0d6cb142fd04dc9a0f812c8362f`, merged at `61a8a7c6d8090bac5df0b711db5c43f4e8b34326`. Release **0.18.393** routes a quoted named-rule details question to a source-unique ID and read-only native rule-document sections instead of the incorrect 165-item inventory. Installed same-question outcome **NOT MEASURED**.

**Verified merged release 0.18.394:** [PR #1390](https://github.com/ienam-smarthome/HomeBrainOS/pull/1390) passed **7/7 CI checks** on exact head `c137b6ce119259dec07b21898eea102954494748` (full Python **6,265 passed, 2 warnings**), merged into main at `7033ecbcf62f39c9e977201afcd155b26b25a8a8`; `hubitat-mcp-ai/config.yaml` reports **0.18.394**. Upstream MCP issue #575 closed with a typed `atDate#` fix for 5.1.6. HomeBrain's previous legacy schedule writer correctly rejected native create but could not schedule Google TV Internet OFF after a relative delay or at a dated time. Candidate restricts native creation to one future dated Switch action after user confirmation, with installed version, typed Rule Machine parent, target resolution, duplicate checks, source-typed changes and confirmation replay. Native result requires a matching persisted rule document, nonbroken status and activation jobs before a success message; even those do not prove future execution/physical Internet effect. Multi-action OFF → 15-minute wait → ON and daily recurring native authoring remain **UNSUPPORTED** and will refuse. No GitHub PR changed live Hubitat/HA/router state. Real first-attempt success/latency, action correctness and model-evidence quality **NOT MEASURED**. This release supports one future single Switch ON/OFF action at a specified clock time or after X minutes, **only** when the installed Hubitat MCP Server verifies version >=5.1.6; compound OFF → delay → ON remains explicitly unsupported. Neither the GitHub merge nor green CI proves a live scheduled rule exists or will fire. See release notes and exact PR checks. Roll back if unverified/partial writes occur. Next: user installs addon 0.18.394 and MCP >=5.1.6; perform read-only named-rule ID 4285 inspection, then only after explicit user confirmation test a single benign scheduled virtual switch. Do not create rules against production Internet controls as an unverified regression test.


## 2026-11-04 — Q1 first-round read-only tool admission v0.18.391 (GREEN MERGED)

**Exact verified release:** [PR #1385](https://github.com/ienam-smarthome/HomeBrainOS/pull/1385) passed **7/7 GitHub checks** on head `ea10c23d16fb4bdc739b7600fe49de66b9f97d6e`, including **6,246 passed, 2 warnings** full Python suite, add-on smoke, metadata and two test/two validation jobs. It merged as `5a43893dc2efd4514a6def640aa2670239885f3c` and that SHA was independently verified at `main`. The maintained add-on version is **0.18.391**. CI proves engineering regressions pass; the new version has **not** been proved installed or evaluated against real household source claims.

**General hypothesis, not an Internet-blocker-specific patch:** The initial read-only provider tool list could contain direct write/control functions or a pre-discovered management gateway before the first model call; a model could waste a round on a proposal correctly blocked by the host. v0.18.391 prunes the **initial** model-visible list to installed read-only tools without adding extra reads or forcing fixed prose. Subsequent explicit discovery can still offer mixed-purpose management gateways with a *verified read operation*, e.g. native Rule Machine documents. Per-call effect authorization atomically rejects all unauthorized writes, and a blocked round retains the old sticky read-only recovery. Tests confirmed native read sources were not lost. Authorized controls, confirmation and natural model-authored synthesis are unchanged.

**Baseline vs candidate honestly separated:** The single previously observed v0.18.390 read-only six-check report took **15.168s** / **4 model rounds**, with **7 read-like receipts** (discovery/local projections included) and **1 blocked model write batch**, while the six source-verified answers were not established. This is **the earlier release's baseline**, not a candidate outcome. There is **no post-v0.18.391 installed first-run response**, independently verified deployed Git SHA, independently source-reviewed factual accuracy, or first-attempt usefulness score. Official factual grounding, causal calibration, hallucination reduction, model-provider comparisons and end-to-end latency improvement remain **NOT MEASURED**. Do not promote synthetic pass counts into answer-quality percentages or Claude equivalence.

**Next Q1 acceptance (operator supplies only read-only Q&A):** Install/update the maintained add-on by the user's ordinary process, then submit *once* in HomeBrain:
`Check the current switch state and brightness level of Hallway Light 1 and Livingroom Light 2 using individually verified device reads. If any value is unavailable or stale, say so explicitly. Do not infer the cause of a past transition. Do not change anything.`
Retain its **first complete natural-language answer plus complete technical evidence JSON** privately; capture observed version, elapsed, tool rounds, actual executed reads and rejected writes from that JSON. Review every value against authoritative returned source data and independently distinguish missing/stale evidence. This is an **ordinary multi-device read-only source-quality sample**, **not** an identical-packet before/after trial or a new 40-packet score. Resume the frozen 40-case Q1/Q2 paired source-review programme only with matched packet hashes, authenticated first responses, and human-checked conclusions. Next code milestone should be chosen from a measured cross-domain failure class, not a new one-off hardcoded incident route.

**Internet blocker:** production Internet blocking stays **DISABLED**. The disposable Virtual Switch and time-bound BAT Rule Machine rule were not independently verified and the historical six-check outcome was incomplete. This GitHub release makes **no** Hubitat, Home Assistant, router or scheduled-rule changes, and does not prove Internet block/restore. No live writes without a separate user authorization. Roll back this release's focused schema admission change if installed model source reads regress.

## 2026-11-04 — Q1 live same-API-prompt v0.18.389 → v0.18.390 receipt comparison

**One observed, ungraded user-supplied live pair:** same normalized API
prompt digest and same Gemma Free model, but `model_delivery_verified=false`,
`first_attempt_verified=false`, `deployed_build_sha_verified=false`
in both envelopes. The old 25,925ms/2-read/5-round/2-blocked-write
receipt compared with v0.18.390's **15,168ms/7-read/4-round/1-blocked-write**
receipt; one recovery-view activation was recorded. Delta -10,757ms
(**41.5% faster on this one pair**); candidate still exceeds the
15-second routine target. API outcome shifted from `success` to
`unresolved` despite both transports returning `success=true`.
No recorded write in either; no verified live Internet block.

**Important unresolved claims:** current hub time is model-derived, not
independently hub-read; current `hub_get_info` receipt is not a source
for MCP server version; latest-backup claim appears older than an
earlier separately reported hub-local source timestamp; test-switch
lookup used a generic rather than the canonical unique label; and
absence of `dated` in rule labels is not evidence that no native
one-time rule exists. A tool discovery receipt does not certify direct
writer availability or authorization. The six displayed answers are
**not source-verified as a set**.

**Verified CI/merge:** [PR #1383](https://github.com/ienam-smarthome/HomeBrainOS/pull/1383) passed **6/6 checks** at exact head `d3ecda6c6ffaa7ec2b9242ac66a1749e754b39d6`, including **6,243 passed, 2 warnings** full Python suite; merged into `main` as `c7aa3a4dbc04dc97596e3bf3a5d7224919641841`, independently confirmed as main head. Add-on version remains **0.18.390**; no runtime change and no independent human-graded factual correctness increase was established.

**Q1 evaluation work:** [Qualitative live-pair review](ANSWER-QUALITY-Q1-PREFLIGHT-LIVE-PAIR-20261104.md)
and generic privacy-bounded
`scripts/answer_quality_live_receipt_diff.py` plus synthetic tests
were prepared to compare honest elapsed, reads, blocked writes, request
outcomes, and API-prompt equality without counting model words as
truth, copying private device content, or publishing an inaccurate
first-attempt score. This work changes **no add-on runtime/version**.
Formal factual-grounding/first-attempt score and model comparison
remain **NOT MEASURED**. Next: CI-gated evaluation PR then a
separate ordinary multi-device Q1 read-only receipt, followed by
source-packet Q2 comparison. Production Internet blocker **DISABLED**.

## 2026-11-04 — installed Q1 read-only six-check failure; generic recovery (v0.18.390 GREEN MERGED)

**Merged previous release:** [PR #1380](https://github.com/ienam-smarthome/HomeBrainOS/pull/1380) passed **8/8** final checks and merged as `cf784f82aaa057b098629a95767b13c4b079bcf2`. The user supplied a live result self-reporting **add-on v0.18.389**. This establishes an installed version string, not independently authenticated deployed Git SHA.

**Measured single live receipt:** At 2026-11-04 ~01:15 UTC, a **read-only six-check** preflight reported hub time `2026-11-04 01:15:26` and **five** checks as not established: hub-local backup timestamp, installed MCP server version, direct virtual-device creator availability, isolated BAT switch, and dated rule. The evidence carried only `hub_list_apps` and `hub_get_metrics` execution receipts; the model-reported clock value was not embedded as an independently value-checked source field in the public trace. It reported `read_only_model_write_blocked=2`, **5 Gemma cloud-free rounds**, **2 executed MCP calls**, **1 discovery**, **23.042s provider**, **2.430s MCP** and **25.925s total**. No Hubitat/HA/router mutation is reported; the blocking boundary held. The transport's `success=true` means the request returned a response, **not** that the six requested objectives were proven or Internet access was blocked.

**Source-completeness assessment:** 1/6 objectives was reported (hub clock), **5/6 unresolved** in this request. Formal source-verified outcomes remain **not measured** because original exact question text, model delivery, independent SHA, and source value details are incomplete (`model_delivery_verified=false`, `first_attempt_verified=false`, `deployed_build_sha_verified=false`). This single 25.9s sample exceeds the charter's target for common status, but cannot establish a median/p95. The earlier **separate** installed v0.18.388 purpose-built native preflight had already source-reported MCP **5.1.5** and 21 hub-local backups (newest 2026-11-03 17:37:05 UTC). This request did **not** repeat/contradict those records; do not silently combine different-time readings into proof of current backup freshness.

**General engineering hypothesis (not an incident-specific preflight route):** The existing atomic read-only write guard stopped the model twice but offered the *same write-capable schema* again. v0.18.390 exposes only present, verified read capabilities on subsequent rounds after the first rejected write batch, keeps that restriction sticky across discovery, and preserves natural model synthesis, the atomic batch-refusal rule, existing authority gates and all tool schemas for separately authorized writes. Fake MCP regressions cover mixed write + read rejection, read recovery, missing reader, and previous authorized virtual-device creation.

**Verified release gate:** [PR #1381](https://github.com/ienam-smarthome/HomeBrainOS/pull/1381) passed **8/8** GitHub checks on exact head `00973a6370b6c86d2406ca8d3c326c813a977889`, including the full **6,234 passed, 2 warnings** Python suite, add-on smoke, metadata, two test jobs, two validate jobs and the offline scorecard. Merged into `main` as `eff0391d48067d6e232445fb702bd43561542fd2` and main/version 0.18.390 independently verified. Initial CI head had 6,233 passing tests and an unregistered metric-name failure, which was corrected before merge. These are engineering checks, **not measured answer quality**.

**Expected effect:** fewer repeated blocked writes and more actual requested read receipts; **real pre/post answer quality, completeness and latency gains NOT MEASURED** until installed same-question receipts are available. Never enable production Internet blocking from this partial preflight. Both offline BAT writers remain disabled, and there is no verified disposable live switch or dated test rule. Next: green-CI merge, installed v0.18.390 read-only acceptance using one exact fixed prompt, then return to Q1 comparable benchmark review / Q2 A/B. Rollback is the focused change if read capability/permission safety regresses.


## 2026-11-04 — generic virtual-device creation contract (v0.18.389 candidate; CI / installed acceptance pending)

**New real failure receipt (supplied by user):** installed v0.18.388
received a specific authorised request for a disposable Virtual Switch,
`HB BAT Isolated Timer Switch 2026-11-04`. The normal confirmation was
queued after three read calls; after user confirmation, HomeBrain submitted
`hub_manage_devices.hub_create_device` with
`deviceTypeId="Virtual Switch"`, a display-name virtual type.
The server returned an explicit **failure**:
"Could not resolve one supported native driver type for Virtual Switch;
no device create request sent." Confirmation execution was **304 ms**;
the first pre-confirm request was **12.879 s** (four Cloud Gemma rounds,
three read tool calls). These are two distinct request phases and
**not** a first-attempt accuracy score. There is **no verified new switch**,
scheduled Rule Machine test or production Internet block.

**General contract correction under development:** The upstream
`hub_manage_virtual_device` is a *direct* tool with a `deviceType`
field, already classified as sensitive by HomeBrain, but fuzzy
discovery can favour the generic `hub_manage_devices` gateway.
Only for positively authorised virtual-device provisioning, offer the
live direct schema to the model; do not invent missing capabilities or
grant a write from discovery. Reject `Virtual ...` display labels
used as generic `hub_create_device.deviceTypeId` before any confirmation,
and check again on confirmation resume. Preserve natural model
argument selection and the existing user-intent, write-master and
confirmation boundaries. No household device or rule was changed
during repository work.

**Hypothesis / metric:** Correct operation selection should improve
the observed failed Virtual Switch case. Offline same-input mock
tests check that the direct tool is available despite bad fuzzy search,
that a wrong native driver ID is blocked, and that missing tools remain
missing. Real after-install first-answer choice, successful creation,
latency, source-verified ownership and **official answer-quality score
are NOT MEASURED**. This is not a claim of Claude-quality parity.
Rollback is to revert the focused v0.18.389 PR if the no-write,
confirmation or tool discovery regressions appear.

**Roadmap remains:** Q1 baseline / fixed source packets and ungraded
first-attempt evaluations remain active; no new incident-specific
publisher rule was introduced. Do not activate production Internet
blocking, turn the test switch ON, create a dated rule, or modify the
router from this release. Re-evaluate only with new authorised,
source-backed read-only receipts when a live source is essential.
CI/merge SHA to be updated from GitHub's exact-head results, never
predicted.

## Internet-blocker read-only preflight PASSED on installed 0.18.388; isolated BAT discovery fix — 2026-11-04 00:36 UTC

**Real user-provided acceptance:** v0.18.388 returned the previously
missing three-source native Rule Machine readiness preflight in
**4.463 seconds**, no language-model rounds and four evidence receipts
(3 remote reads, one typed local projection). Sources:
MCP `initialize.serverInfo.name=hubitat-mcp-rule-server`,
`version=5.1.5`; `hub_list_backups(scope=hub_local)`
returned **21** local backups and newest source-timestamp
`2026-11-03T17:37:05+00:00`; both `hub_get_tool_guide` sections
`set_rule_reference` and `builtin_app_tools_rules` were reported
readable. `preflightEvidenceComplete=true`,
`investigation_coverage.status=preflight-source-complete`,
`questionResolved=true`, `readinessForMutation=false`.
No backup, device, native rule or router setting changed.
At the collector receipt `2026-11-04T00:36:01Z`, that source backup
was ~6h59m earlier, but no independent **hub clock** was checked, so
the installed writer's backup freshness prerequisite is **not fully
verified**. Guide availability is not a proof that every write field
is supported. Source-complete preflight is **not** authorisation to
run any live write or proof of native dated-rule firing/network blocking.

**Offline discoverability fix merged GREEN:** [PR #1378](https://github.com/ienam-smarthome/HomeBrainOS/pull/1378)
tested at exact head `c732a426f567ad0aca3204c3a0ecd0b9efc29a32`
with **6/6 CI checks green**; the full Python suite reported
**6,224 passed, 2 warnings**. Merged as
`b8eb8c0c012ab1f0826da272c9d4005b654fa451`.
Only the disabled offline BAT compiler/tests/documents changed;
HomeBrain runtime is **still 0.18.388**.

**Next offline preparation finding (not a live incident patch):**
the disabled `scripts/native_rule_dated_candidate.py` generated a
rule name with UTC slot and hash but no terminal
`(One-time YYYY-MM-DD HH:MM)` marker. The maintained
`native_rule_inventory_source.py` checks exactly that suffix.
A future BAT created under the old name would not be discoverable
as a one-time rule in that routine's later read-only inventory.
The merged offline change aligns the terminal suffix using the Hubitat-local
due minute, retaining the UTC slot and hash (including for DST
ambiguous local minutes), and tests that the real inventory projector
recognises the planned label while refusing the legacy form.
Only the **offline, disabled** BAT candidate, tests and documents
change. HomeBrain add-on stays **0.18.388**.

**Still missing for a live harmless BAT:** independently observed hub
clock and backup age; confirmed creation/ownership of a **new
isolated** virtual test switch (never repurpose the existing
MCP-managed household Virtual Switch); explicit user authorisation
for creating that switch, changing it to ON and creating **one**
scheduled OFF native rule; stored date/time/target readback,
pending-job observation and future OFF command/state evidence.
The BAT defaults to `NATIVE_DATED_ENABLED=False`, does not
run actions immediately and does not automatically clean itself
up; any future cleanup needs verified completion and separate
authorisation. **Do not** enable production Internet blocking,
change existing automations, or make router changes. Continue
the Answer Quality roadmap without counting this read-only
preflight as a first-attempt accuracy score.


## Native Rule Machine multi-source read-only preflight routing — v0.18.388 GREEN MERGED (2026-11-04)

**Repository gate verified:** [PR #1376](https://github.com/ienam-smarthome/HomeBrainOS/pull/1376)
merged as `c89b0493d19a47e2b7ce3297a3da648c2d2cf51c`
with **7/7 CI checks passed on exact final PR head**
`426ee66afa1c205844f761b6a15ab246c0dd5404`.
Full Python suite **6,223 passed, 2 warnings**; metadata, offline
scorecard, add-on smoke, test and two validation checks all succeeded.
An earlier head failed only the architecture module-map registration,
which was corrected before the green final run.

**Current state:** maintained HomeBrain add-on source **0.18.388**,
not yet evidenced as installed; original v0.18.387 native parent
ID 169 remains source-verified. Production Internet-blocker
**DISABLED**; read-only preflight cannot authorize scheduling.
No live Hubitat/HA/OpenWrt changes.

**One next installed acceptance:** install v0.18.388 and use the exact
same read-only version/backup/guides question recorded below in a
fresh HomeBrain topic; return natural answer and full Technical Details
JSON, omitting secrets. Inspect `typed_native_rule_readiness` fields:
`mcpServerVersion`, `latestHubLocalBackupUtc`,
`toolGuideAvailability`, `preflightEvidenceComplete`, and
`readinessForMutation=false`. Missing source remains unverified;
verify live backup freshness against independently reported hub time
before a later separately approved disposable test. Do not reuse
the existing MCP-owned household Virtual Switch. Even a complete
read-only preflight does not prove native dated execution or OpenWrt
enforcement.


**Installed v0.18.387 user result at 00:19:25 UTC:** another read-only
native Rule Machine parent inventory was returned in **2.970 seconds**
with zero model rounds, five tool receipts (four remote rule/app
inventory reads plus typed projection), native parent 169 verified and
zero exact one-time suffix matches. The technical prompt fingerprint
was **different** from the previous parent inventory question:
`d166f6d6f0b6542856b4a39c54f4289b8f2d77573a67151014dba1533399360b`.
The original text of this latest prompt is **not exposed** in its JSON;
the sequence followed our explicit backup/version/tool-guide preflight
question, but the response **did not read** MCP serverInfo, hub backups,
or tool guides. Those three readiness obligations are **not measured**.
No modifying tools were called and production Internet-blocker is
**still disabled**.

**Reproducible general routing defect:** the existing native inventory
classifier independently matched `Rule Machine`, `backup inventory`
and the question's `which` tool-guide sections, incorrectly treating
a multi-source preflight as a rule/app inventory. The merged v0.18.388 release
adds a **separately scoped read-only readiness objective** ahead of
single-subject inventory, recognizing at least two positive read
obligations (version, backup, guide) rather than negative instructions.
It obtains MCP version from *serverInfo returned by MCP initialize*
only with the exact upstream `hubitat-mcp-rule-server` identity;
calls only `hub_list_backups(scope=hub_local)` and the two read-only
`hub_get_tool_guide` sections, and publishes **only** timestamp/count,
guide-availability booleans and version. No guide acknowledgements,
backup filenames, private settings, cloud model rounds or write calls.
Missing/partial source fields must be reported unverified; a completed
readiness answer **never authorizes native writes**.

**Baseline:** latest wrong-objective response in 2.970s with **0/3**
readiness source classes covered. **Post-change installed performance,
correctness, and exact MCP Rule Server version: NOT MEASURED.** Unit
fixtures and CI verify only the new route's intent isolation, source
shapes and no-write/redaction invariants. Runtime source version moves
to 0.18.388 because the read-only behaviour changes. A future
read-only answer+Technical JSON is still needed for live acceptance;
a separately approved *new* disposable virtual-switch BAT remains
necessary for execution verification. Never reuse the existing
MCP-owned switch from v0.18.381. The permanent Answer Quality roadmap
is preserved; this is one general objective-routing repair.


## Installed v0.18.387 native Rule Machine parent — SOURCE-VERIFIED PASS (2026-11-04 00:09 UTC)

**Real user-supplied read-only acceptance:** exact repeated native Rule
Machine inventory question under installed HomeBrain `version=0.18.387`
returned `success=true`, `elapsed_ms=2940`, `model=null`,
`tool_calls=5` (four successful read-only MCP calls plus local typed
projection), `confirmation_required=false`. Exact identity:
`parents=[{appId:"169",appTypeId:"18",namespace:"hubitat",
name:"Rule Machine",proof:"source-typed-installed-app-summary"}]`,
`candidateParents=[]`, `summarySourceChecks=[{appId:"169",
typeProofGap:null}]`, `catalogClassConflicts=[]`,
`parentIdentityComplete=true`. Under the returned **complete** current
rule and app pages, `oneTimeRules=[]`, `oneTimeMatchCount=0`
for the **exact** `(One-time YYYY-MM-DD HH:MM)` suffix.
`investigation_coverage.status="inventory-complete"`,
`questionResolved=true`, `evidenceComplete=true`. No writer, rule or
device mutation. This **closes the installed native-parent source-identity
preflight**, not native rule creation, date firing, one-time lifetime
cleanup, or Internet blocking.

**Paired repeated-question observations** (same
`normalized_prompt_sha256=a1afac645cff64baed3516beacebb46431175834cd4c334457d141ab2f693a83`):
v0.18.385 **25.650s**, 6 Gemma rounds, 10 tool calls, parent unverified;
v0.18.386 **3.611s**, no model, 5 tools, parent unresolved due to
a class-catalog conflict; v0.18.387 **2.940s**, no model, 5 tools,
native parent verified. Observed end-to-end reduction **88.5%** from
v0.18.385 to v0.18.387 (**n=1 paired question**, not a population
distribution or first-attempt score). Independent first attempt and
deployed commit cannot be certified because
`request_provenance.first_attempt_verified=false` and
`deployed_build_sha_verified=false`; user-submitted installed version
is a self-reported app field. No model was invoked on the final read.
Q1 quantitative acceptance thresholds are **not recalculated**.

**Next missing gates, in priority order:** (1) read-only source-reported
installed MCP server version / native rule tool-guide contract and
fresh hub-backup timestamp; (2) confirm independent ownership and
isolation of a **new** disposable test switch, *not* the one
existing MCP-managed Virtual Switch verified under v0.18.381;
(3) seek separate explicit user consent for that exact harmless
switch ON and one native dated Rule Machine create; (4) verify stored
date/action/readback, pending native job, independently timestamped
future OFF transition, reboot/recovery and cleanup/ownership;
(5) only later independently test and commission OpenWrt
enforcement. `scripts/native_rule_dated_candidate.py` and
`scripts/native_rule_delay_candidate.py` remain **OFFLINE ONLY**
and disabled. No live HomeBrain/Hubitat/HA/router changes authorised
by the identity result.

**Next one read-only HomeBrain question** (new topic, complete answer
and Technical Details JSON):
```text
Read-only preflight for a future disposable native Rule Machine timed-switch test.
Report the installed MCP Rule Server version only if its own read-only
status/info source exposes a version. Otherwise mark it unverified.
Report the newest Hubitat local backup timestamp using read-only backup
inventory, or say why backup freshness cannot be verified.
Check whether the read-only MCP tool guides for set_rule_reference and
builtin_app_tools_rules are available; report which sections are readable,
without copying acknowledgement tokens or private configuration.
Do not create a backup, virtual device or rule. Do not run, change,
pause or delete anything and do not access router controls.
```
The preflight source response can be partial; missing fields must not
be represented as passes. Retain the permanent Answer Quality roadmap.


## Internet-blocker native class catalog consistency — v0.18.387 GREEN MERGED (2026-11-03)

**Verified:** [PR #1373](https://github.com/ienam-smarthome/HomeBrainOS/pull/1373)
merged as `2cf6399b090919aa51b3656748fe3385c82a0d7a`
after **8/8 CI checks green on exact head**
`2d1480f43f4e6f6d91c36494ae995ff751573d69`
(**6,212 Python tests passed, 2 warnings**, including add-on smoke,
validation, metadata, offline scorecard and repeated test gates).
The maintained add-on source version is **0.18.387**.
No live Hubitat/HA/OpenWrt/device/rule write occurred.

**Next installed checkpoint:** install v0.18.387 and repeat the
**exact v0.18.385/386 read-only native Rule Machine inventory question**
in a fresh HomeBrain topic. Provide full natural answer and Technical
Details JSON. Check `parents`, `summarySourceChecks`,
`catalogClassConflicts` if any, and `oneTimeMatchCount`.
If parent 169 remains unverified, the sanitized catalog witness,
not another guessed source page, determines the next source-contract
step. Do not submit a write or interpret a parent-resolution result
as proof of a scheduled block. This is a paired repeat, not a fresh
first-attempt acceptance sample.


**Installed paired read-only test v0.18.386:** 3.611s, zero model
rounds, five logical tool calls vs v0.18.385's 25.650s, six rounds,
ten calls on the same prompt (85.9% shorter observed elapsed, **n=1**
pair; not a controlled distribution or certified first attempt). Source
projector found parent candidate app 169, appTypeId 18; returned
zero exact one-time suffixes from complete rule/app listings.
Exact `hub_get_app_config(169,summary=true)` read succeeded but native
parent remained unresolved due to `native-app-summary-catalog-conflict`.
The private diagnostic JSON did not include raw catalog class entries;
actual installed conflict details **are still unverified**.

**General source-contract finding and merged fix:** the upstream MCP
`hub_list_apps(scope=types)` builds from community userAppTypes plus
native systemAppTypes; the built-in class can have `system=true` and
`isBuiltIn=true` with no `namespace`. HomeBrain 0.18.386 treated
`namespace=None` as a contradictory namespace even when thin
`hub_get_app_config(summary=true)` independently attested the
installed app's namespace. The 0.18.387 merged implementation distinguishes
**missing** from **explicitly conflicting** namespace, accepts a
source-typed summary only with exact ID/type/user/root identity, and
retains hard refusals for explicit foreign namespace, wrong class
name and any user-code flags. A bounded, name-redacted conflict witness
is reported if a real mismatch remains; no added MCP reads/cloud rounds.

**Acceptance pending:** source tests and CI first; then one same-question
read-only installed receipt with native parent verification or typed
conflict details. No real timed switch test, one-time execution or
OpenWrt blocking is established. The offline BAT scripts remain
disabled, and a live harmless virtual-switch test needs independent
written approval. No household automation/device/network changed.
The permanent Answer Quality Q1/Q2 roadmap remains active.


## Internet blocker source-verification routing — v0.18.386 GREEN MERGED (2026-11-03)

**Verified repository result:** [PR #1371](https://github.com/ienam-smarthome/HomeBrainOS/pull/1371)
merged as `a9cdf4e6df4ee66ec8e61a37d9746af2f752e369`
after **7/7 CI checks green on exact PR head**
`991b99d4bebb4d048a8ae019f27a7cd645093fc3`: **6,197
Python tests passed, 2 warnings**, plus secondary test, two
validation jobs, add-on smoke, metadata and offline-scorecard.
Add-on source version **0.18.386**. No device, automation, rule, HA
or router/network mutations occurred.

**Next single read-only installed acceptance:** install v0.18.386, then
repeat the **exact same inventory/identity question** from 23:37 UTC
without changing wording. Capture complete public response and
Technical Details JSON. Confirm source-verified parent class/namespace,
exact one-time suffix count, inventory scope and elapsed/model rounds.
Do not count this repeat as a new first attempt; it is a paired
before/after observation. If current MCP still omits `namespace`,
report that evidence gap instead of authorizing a writer.
The production Internet blocker stays disabled pending independent
dated-rule scheduling and network enforcement evidence, and a separate,
specific approval for any disposable BAT.

**Live user-supplied v0.18.385 result:** read-only parent/one-time inventory
question returned 25.650s, six `gemma4:31b` Ollama-free model rounds,
ten tool calls, parent *candidate* 169 but no direct native namespace proof.
It unnecessarily invoked `hub_get_source(id=18,type=app)` three times
for inaccessible built-in Groovy and claimed "42 one-time" when the
receipt showed only an overall rules list, not 42 matching dated suffixes.
`hub_get_app_config(appId=169,summary=true)` was **not called**;
`request_provenance.first_attempt_verified=false`, so not an accepted
first-answer benchmark. Developer's MCP 5.1.5 fix itself is not disproved.

**General code cause and merged fix:** bare "why" in the inventory
classifier diverted a request asking **why source identity was unverified**
to the generic model deep-analysis path. New source-objective classifier
reserves deep analysis for actual execution/causal questions. The typed
read-only inventory path then calls the existing 3 bounded source lists
plus at most one exact lightweight summary if parent identity is
unresolved; prints source-verified type/namespace and only exact
one-time-name matches; no costly Groovy source/model rounds or writer.
Synthetic orchestrator tests distinguish identity-coverage from
execution-cause prompts and prohibit mutation.
**Real after latency/answer correctness: NOT YET MEASURED** until
v0.18.386 is installed and read-only acceptance is provided.

**Internet-blocker safety:** this still does not prove actual installed
MCP version, namespace, native dated trigger, switch OFF due event,
or OpenWrt enforcement. No live Hubitat/HA/router changes. Both
dated and delay BAT scripts remain disabled. No live test-device
creation or scheduled action without separate user authorization.
Answer Quality charter remains active; this work corrects a general
source-selection failure observed in a real answer.


## Internet-blocker MCP 5.1.5 read-only native-parent fix — v0.18.385 GREEN MERGED (2026-11-03)

**CI and merge:** [PR #1369](https://github.com/ienam-smarthome/HomeBrainOS/pull/1369)
tested at exact head `e54e5f1cb3230e10c8e505719536e851baa33317`
with **6/6 checks green** (Full Python **6,189 passed, 2 warnings**;
Hubitat MCP AI test, add-on smoke, metadata, validate, offline-scorecard).
Merged as `d279b98a63d3a48653575818893c533d48482b74`.
Maintained add-on release **0.18.385**. Initial CI metadata mismatch
was corrected by updating both README version declarations before the
final green exact-head run. No hub, Home Assistant, OpenWrt or device
writes occurred.

**Installed after-result: NOT YET VERIFIED.** Green offline tests show
that the new flat `namespace=hubitat` source form can resolve an exact,
unique native parent and reject conflicting identity. The user's installed
MCP version, real summary fields, dated scheduling, future firing and router
blocking remain unverified. **Next single read-only user capture** after
installing v0.18.385: identify the installed native Rule Machine parent and
list existing one-time Rule Machine rules using the read-only inventory,
allowing its one thin `hub_get_app_config(summary=true)` fallback; return
the complete natural answer and Technical details JSON. Verify source
scope and identity, then ask separately for approval before a newly
owned disposable virtual-switch BAT. No real access-blocking or production
writer enablement. Answer Quality programme continues independently.


**Source-contract defect:** upstream PR #576 emits direct `namespace` in
`hub_get_app_config(summary=true)`, but v0.18.384's live inventory
projector only trusted a nested `appType` object, which the *thin*
summary need not provide. The existing offline BAT parent finder already
accepted flat identity; production read-only diagnostics therefore lagged
the developer fix. v0.18.385 candidate teaches the common inventory
projector to use exact flat `id/type/namespace/user` plus independent
instance ID, with nested and catalog contradiction checks and synthetic
no-write tests. No form read, model/prose change, new cloud calls or
live writes. **CI and merge are now green as above; installed acceptance and
network effect remain not measured**. Version changes only
because maintained runtime read-only behavior changes. The original Q1
programme continues alongside the explicitly resumed blocker work.

**User read-only evidence received separately:** multi-device status
question (2026-11-03 23:25 UTC) reported two scoped current switch/level
reads, but inspected history for one device only, with
`sourceScopeComplete=false`/`questionResolved=false` and a green
success flag. The asserted automation cause exceeds the limited
command-history scope; do **not** count it as certified first-attempt
quality. Preserve this Q1 candidate for later general source/answer
review, without holding up the safety-first Internet-blocker track.


## Q1 scorecard latency-cohort separation — verified GREEN MERGE (2026-11-03)

**Verified:** [PR #1367](https://github.com/ienam-smarthome/HomeBrainOS/pull/1367)
merged as `2c402515f55b22d9d42d09b01cddd84428d60f5f`.
Exact tested PR head `59425745745fc9be654dc4e9ef1e32beb0a45d38`:
**6/6 checks GREEN**, **6,175 Python tests passed, 2 warnings**,
plus add-on smoke, metadata validation, two validate jobs and offline
scorecard integrity. Runtime add-on remains **0.18.384**. No live
Hubitat/HA/OpenWrt changes, model prompts, MCP calls, publication logic,
writer paths or secrets involved.

**General measurement correction:** The old scorecard pooled latency from
40 curated **offline-only** model packets with 13 nominal legacy live
status/control/investigation/rule cases. That pooled median/p95 cannot
test either the status/control 15s or complex investigation 45s charter
target. The new `latency_by_cohort` reports separate counts, medians, p95s,
nominal target and explicit observational/non-verdict status, preserves
the original pooled numbers with a mixed-scope warning, and leaves
missing timing `not_measured`. Synthetic regression tests verify that
offline model timings cannot be counted as live performance. The
cohort labels are case definitions, **not proof of live-run provenance**.
No real quality or population-level latency gain is claimed: formal
frozen first-attempt denominator **0**, live cohorts **not measured**.

**Next unfinished original roadmap milestone:** Q1 independently reviewed,
new first-attempt status/control and investigation receipts with exact
question fingerprint, response/tool evidence, tool-call timing and
published-vs-model distinction where present; then Q2 same-packet Gemma
versus alternative model comparison. Do not repeat the already
closed named-dimmer regression or count green CI as answer quality.
A useful next untested **read-only** legacy question is
`Compare the states of Hallway Light 1 and Livingroom Light 2.`
(case `multi_device_named`), requesting the natural answer and complete
technical JSON in the private chat. No mutation or Internet blocker
activation is authorized. Rollback: revert PR #1367.

## Native one-time Internet-block BAT candidate — offline preparation merged GREEN (2026-11-03)

**Verified release-independent merge:** [PR #1365](https://github.com/ienam-smarthome/HomeBrainOS/pull/1365) tested at exact head `e1ea29a4194d7daf579141b1885cc9e32a4844de`, merged as `53c4daa60c01fb482303a02279542a9013322d57`. **5/5 CI jobs green**, including **6,173 Python tests passed, 2 warnings**, metadata, add-on smoke and offline scorecard integrity. Source add-on version **0.18.384 unchanged**; code is scripts/tests/docs only and no production import. The fresh disabled script `scripts/native_rule_dated_candidate.py` includes native date (yyyy-MM-dd) + hub-local time trigger / OFF action, strict source-typed parent summary fallback from upstream MCP 5.1.5, DST-safe minute alignment, pre-existing fresh-backup gate (NO backup creation), duplicate/timeout/refusal logic, and strict rule readback. It **never issues Run Actions or deletes a rule**. Prior disabled delay script unchanged in runtime. `NATIVE_DATED_ENABLED=False`, `NATIVE_DELAY_ENABLED=False`; no live Hubitat/HA/OpenWrt mutations.

**Current upstream capability:** upstream PR #576 merged and MCP 5.1.5 released, fixing both date-typed `atDate#` and installed app `namespace` identity. User says developer update installed; **installed version and parent summary still need a read-only source receipt** before any live BAT; earlier app 169/type 18 inventory could not verify parent. Read-only next step described in [native dated preflight](NATIVE-RM-DATED-BAT-PREFLIGHT.md). Do NOT repeat Rule 4259/action reads or existing owned-device inventory. New BAT virtual switch must be separately created/approved; do not repurpose an existing MCP-owned switch. Native scheduled job verification, actual trigger firing, reboot/cleanup, and network-level block effects remain UNVERIFIED. Production Internet-block writer is **not enabled**. This project is resumed at the user's direction, while the permanent Q1/Q2 Answer Quality programme remains active independently. Green synthetic CI is not a live behaviour test or an answer-quality score.


## Internet-blocker project RESUMED after upstream MCP 5.1.5 fix — offline dated BAT only (2026-11-03)

**New user authorization:** The user explicitly **resumed research and safe repository development** on delayed Internet blocking after the developer reported a fix. This supersedes older entries saying the project is paused; it **does not** approve creating/running/deleting any live Hubitat/HA rule, changing an existing switch, or blocking a real device. The standing Answer Quality charter remains active in parallel.

**Confirmed developer fix:** [upstream MCP PR #576](https://github.com/kingpanther13/Hubitat-local-MCP-server/pull/576) merged as commit `79ac8c1c67309adfae5a3a8861f754fe6116e4f4`; version **5.1.5** released; related [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) closed. The server now accepts date-typed `atDate#=yyyy-MM-dd` for a one-time Rule Machine Certain Time trigger and emits source-typed native installed-app `namespace` in `hub_get_app_config(summary=true)` (full app config also returns appType.name/namespace). Developer reports successful C-8/C-7 live tests; **the user's installed version/typed identity/dated-trigger execution have NOT been independently read in this conversation**.

**Architecture:** Prefer native one-time **dated trigger + OFF action** over triggerless Delay → Run Actions. The older delay writer stays disabled. New [source-grounded dated BAT preflight](NATIVE-RM-DATED-BAT-PREFLIGHT.md), `scripts/native_rule_dated_candidate.py` and synthetic regression tests are **offline-only**; `NATIVE_DATED_ENABLED=False`, no production import/version bump, and no live hub/device/network changes. The shared offline parent verifier now uses exact `hub_get_app_config(appId,summary=true)` identity (`id`, `type=Rule Machine`, `namespace=hubitat`, `user=false`, joined to a separately sourced instance ID) **only** if the built-in type list lacks the class, never if another typed record contradicts it. Negative tests reject missing/mismatched/source-failed summaries. BAT logic validates local date/time across GMT/BST, creates no backup implicitly, refuses duplicate/ambiguous writes, verifies exact native saved fields, checks reported native scheduled jobs and never calls Run Actions or auto-deletes.

**Critical outstanding gates:** A one-time **read-only installed parent summary** and installed MCP version (where source-exposed); verify type/namespace with existing app inventory; only then separately approved *new disposable, MCP-owned virtual-switch* BAT with source-timed action/trigger verification and cautious cleanup. Existing MCP-owned switch remains untouched. A reported virtual OFF is **not evidence of a real Internet block**, and producer/scheduling/reboot/expiry evidence remains unknown. Do not activate production Internet writer or update a real block target based on upstream test results alone. CI/merge pending until exact-head checks pass.


## Installed v0.18.384 named-dimmer regression acceptance — PASSED (2026-11-03 22:40 UTC)

**Real installed read-only user capture:** v0.18.384, same *already registered and previously failed* `status_named_dimmer` question, unchanged server-submitted SHA-256 `0b12a9714e4db971b921bd8e5ddecd8b2cb33d8cf607a08646bf7c52ab5417f6`. One targeted `hub_read_devices → hub_list_devices` call used **`format="detailed"` and no unsupported `detailed/offset`**, `labelFilter`, and returned one target-matching candidate. Read receipt `success=true`, `effect=read`, `mutates=false`. Local `homebrain_resolve_device` also succeeded; its typed `reportedDeviceState` included source-reported `switch` and `level` values, matching the concise model answer. For public repository privacy, **omit the private household label/device ID and current reported attribute values**; keep full diagnostic details only in the private chat. `metrics.outcome=success` is appropriate **for this request**; two receipts, only one remote device-list read, no Hubitat modifying operations. `request_class=live-read`.

**Wall time 9.523s**, under charter <15s status target for this single execution; three free Ollama Cloud Gemma 4 31B model rounds, `paid_rounds=0`, 4.781s aggregate provider, remote targeted tool 4.306s, local resolver receipt 4.312s (nested, **do not sum those as separate costs**), discovery 0.351s. **Before** v0.18.383: 7.177s, four model rounds, two failed receipts, no verified switch/brightness, wrongly green outcome. **After** v0.18.384: 9.523s, three rounds, source-backed correct-answer content. This is **measured task completion/grounding improvement**, **not latency improvement** (success took 2.346s longer); single samples do not establish median/p95.

**Claim scope:** Source-attested Hubitat driver state at read/receipt time only, not physical connectivity, current real-world light emission, state attribute event timestamps or actual energy consumption. For an off dimmer, `level` is the stored reported brightness setting, not proof the lamp is illuminated at that percentage. The model answer was clear and compact. The first targeted-tool receipt exposes only the switch scalar; the *subsequent verified resolver* receipt includes both switch and level—use it for value-level review. Original request's `model_delivery_verified=false`, `first_attempt_verified=false` and `deployed_build_sha_verified=false` remain; **repeating this case after the fix is a regression acceptance, not a new independent first-attempt Q1 benchmark entry**. Do not include it in first-attempt denominator or assert population-level quality gains; original formal Q1 scores remain **not_measured**.

**Workflow:** v0.18.384 fix [PR #1362](https://github.com/ienam-smarthome/HomeBrainOS/pull/1362) was already merged and all 6 required jobs green; this entry records the independently observed installed-after result. **No new code or version bump required.** The ongoing original mission is cross-domain real Q1 source review, then same-evidence Q2 paired reasoning comparison and Q3 measured latency/publication simplification. User explicitly paused the Internet-blocker, so **do not resume it**. No further named-dimmer rerun is needed.


## v0.18.384 — native device-list contract and unresolved lookup fixed (GREEN MERGE, installed acceptance pending)

**Verified merge 2026-11-03:** [PR #1362](https://github.com/ienam-smarthome/HomeBrainOS/pull/1362), tested exact PR head `0ddb2328c61f2a26da6f105a2b979c3b149a2d98`, merged main commit `c81087e549baae92a8cfa45dbb5205a3e2770264`. **6/6 required jobs green** (4 workflows): Full Python **6,142 passed, 2 warnings**, Hubitat MCP AI tests, validate, smoke, metadata and scorecard integrity. Version **0.18.384**. Upstream-native device list accepts `format/cursor`, returns `nextCursor`; the shared client strips legacy `detailed/offset` and handles numeric source cursors, rejects conflicting/invalid pagination. Failed device identity reads now record `device_resolution_source_failed`, yield `outcome=unresolved`, and failed evidence receipts do not support live device claims. Existing model-led synthesis, write gates and read-only default unchanged.

**Observed real before (installed v0.18.383):** registered `status_named_dimmer` question exact submitted hash, two failed resolver receipts, 7.177s wall, 4 free Gemma rounds, no current switch/level verified, green Success badge incorrectly shown. **Measured live after on installed v0.18.384: NOT MEASURED**. The raw upstream failure was not returned, so the source diagnosis is contract-backed rather than direct error-code proof. Green CI does not prove user device is reachable nor a first-attempt quality score. No home hub modifications. The separately paused Internet-blocker remains untouched.

**Next read-only regression acceptance (repeat case, not a new first attempt):** After installation, ask exactly `Read the current switch state and brightness of Livingroom Light 2.` in New topic. Return complete natural answer and Technical details JSON. Check native `format="detailed"` (no `detailed`), successful exact ID source, switch/level from real data, honest `outcome`, prompt fingerprint, wall latency. A failure is to be investigated from raw source status, not solved by endless prompt wording or fabricated values. Continue Q1 cross-domain measurement and then Q2 same-packet blind model review under the permanent charter.


## Q1 installed v0.18.383 named-dimmer status failure — shared MCP wire contract correction (2026-11-03 19:39 UTC)

**Real installed capture:** exact registered legacy `status_named_dimmer` question `Read the current switch state and brightness of Livingroom Light 2.` returned “current-turn evidence does not establish switch state or brightness”. Source receipts: failed `hub_read_devices → hub_list_devices` with `labelFilter`/detail-only fields and internal `detailed=true`, plus failed `homebrain_resolve_device`; no state verified and no modifications. `metrics.outcome=success`/positive badge was **wrong** for this unresolved question. **7.177s wall**, 4 free Gemma rounds, two tool receipts; official model-input, deployed SHA and first-attempt flags all false. The submitted-question hash `0b12a9714e4db971b921bd8e5ddecd8b2cb33d8cf607a08646bf7c52ab5417f6` is only HTTP question matching. **Do not infer the target is deleted or offline; no live value is established.**

**Source diagnosis:** Upstream `kingpanther13/Hubitat-local-MCP-server` device-list implementation explicitly rejects unknown argument names, and supports `format="detailed"` / `cursor`, NOT HomeBrain's previous `detailed` / `offset`. A raw upstream error was not included in the historical receipt, so the specific backend rejection is not directly attested by that run. This is a **general device read contract mismatch**, not a Livingroom-specific identity bug. HomeBrain's MCP boundary now removes legacy arguments, maps to source-supported keys and maintains the detailed-vs-summary reported state field invariant. A failed source resolver read increments a fixed privacy-safe `device_resolution_source_failed` counter, receives `outcome=unresolved` and cannot support a live-state claim. [Release note and rollback](../hubitat-mcp-ai/CHANGELOG-0.18.384.md). Existing model-led natural answers, source refusal on inadequate data and write gates preserved.

**Before:** one live registered-name lookup unresolved at 7.177s, wrongly green success despite two unsuccessful source reads. **After (branch/offline):** strict wire contract/rejection recovery tests and outcome tests. **Installed v0.18.384 after-result NOT MEASURED**, no source-graded accuracy improvement claimed. Need CI/merge confirmation and separately captured installed read-only acceptance. Repeating the *same* question is **regression acceptance**, not a new independent frozen Q1 first-attempt sample. Internet-blocker work remains paused.


## Q1 source-value evidence and polling diagnostics v0.18.383 — MERGED / installed after not measured (2026-11-03)

**Verified release:** [PR #1360](https://github.com/ienam-smarthome/HomeBrainOS/pull/1360), exact tested head `0b59b5a90a1362eba53fe6536051636d1182af6f`, merge `898d29d360f68719cbbcd2425d4fab92ef933fa7`; **6/6 CI jobs green**, **6,134 Python tests passed, 2 warnings**, add-on container smoke, metadata and offline scorecard integrity green. Runtime source version **v0.18.383**. Common Hub Information Driver status reads now attach only source-successful, exact-scope, privacy-allowlisted scalar values and units to technical receipts; raw label/ID/IP/arbitrary alerts/secret fields excluded, and no inferred zero/healthy/up-to-date from missing evidence. The same model-led natural answer remains unchanged. The tool also reports actual number of internal polls, configured sleeps and refresh/update-check commands; reaching a read deadline does **not** masquerade as verified firmware settlement. No extra MCP/model round and no live Hubitat/HA changes were made during development.

**Measured real before** remains one v0.18.382 frozen exact question: submitted hash matched, 17.425s wall (above <15s status target), two free model rounds, one local Hub Info snapshot (9.991s), field-name-only public receipt, no independent source-value grade; model input, deployed SHA and first attempt not authenticated. **Installed v0.18.383 after: NOT MEASURED.** Cross-domain factual grounding/first-useful rates and Claude gap remain **not_measured**. Green CI establishes code safety/test fixtures, not better reasoning or lower latency. [Source-bounded Q1 review](ANSWER-QUALITY-Q1-HUB-HEALTH-REVIEW.md) and [release detail](../hubitat-mcp-ai/CHANGELOG-0.18.383.md).

**Next original roadmap step:** Q1 evaluate a separate unchanged frozen read-only legacy question, preferably `Read the current switch state and brightness of Livingroom Light 2.` (`status_named_dimmer`), on installed release. User supplies one complete answer + Technical JSON. Verify request-provenance hash, actual tool/issuer data, clear output, wall latency and read-only classification; only grade groundable fields with source-attested receipts and independently reviewed claims. Do not recycle repeated hub-health acceptance as first attempt or request Internet-blocker work. Once sufficient Q1 source-complete pairs exist, advance to Q2 same-packet model comparisons and Q3 latency/gate simplification without ad-hoc case patches.


## Q1 registered hub-health observation — exact API question, source values not retained (2026-11-03 18:28 UTC)

**Real installed v0.18.382 capture received:** registered legacy case `broad_hub_health`, question `What is the hub health status?`, SHA-256 `b586998f15c01644355754722ae36cce273a5026d2c436046e6a441b05ebf23c` matches exactly the `request_provenance` submitted-question hash under `collapse-whitespace-v1`. Source status `homebrain_hub_info_snapshot` was successful read-classified `authoritative_hub_info_snapshot`, but **technical evidence contained only field names**, not individual source values. The readable output covered firmware, performance/resources, radio/Matter and general alerts; no per-field factual accuracy can be independently graded from the published receipt. **Natural first-answer usefulness was qualitatively good, not formally graded**: `first_attempt_verified=false`, `model_delivery_verified=false`, `deployed_build_sha_verified=false`. Two free Ollama Cloud Gemma rounds were observed; no model-free deterministic route. The final wording's exact model-versus-host derivation is not authenticated.

**Measured single-sample latency:** 17.425s wall / 17.383s agent, above under-15s common-status target. Provider 4.987s, one local driver refresh/poll path 9.991s, tool discovery 2.385s, cumulative MCP HTTP 12.369s (instrumentation categories **overlap**, do not sum). This is **one recorded execution, not median/p95**. A successful tool receipt does not independently prove "no active alerts"/"firmware current". [Private-data-free Q1 review](ANSWER-QUALITY-Q1-HUB-HEALTH-REVIEW.md) records observed versus unverified dimensions, without publishing household values.

**General v0.18.383 candidate:** Give the *same source-typed Hub Information Driver tool* a strict allowlisted, scope-matched public receipt of reported non-private scalar metrics (only if actual values present), plus internal poll/read/wait/refresh counts. Never export IP, device ID, source label, arbitrary alert messages/credentials or nonstandard statuses; missing/invalid means unknown. No extra MCP/model rounds, no language templates, no altered natural reasoning or shortened driver polling. Intended effect: honest same-packet, per-value Q1 grading and better latency attribution, **not a claim that v0.18.382 values were verified**. Synthetic tests cover multiple scopes, units, null/bad values, privacy and no extra calls. CI/merge and installed after-result pending as of candidate; official denominator-based accuracy/usefulness still **not_measured**. Do not restart Internet-blocker or add case-specific language patches.


## Q1 API-submitted prompt provenance v0.18.382 — merged, live acceptance pending (2026-11-03)

**Verified release:** [PR #1358](https://github.com/ienam-smarthome/HomeBrainOS/pull/1358), exact tested head `96183e34a5566482bedfdbec061865975e13da17`, merge SHA `6f3fa751dfa194e287ba8c29b8e39a8795bcd6bf`. **All 6 required CI jobs green**, including **6,124 Python tests passed, 2 warnings**, Hubitat MCP AI tests, add-on container smoke, metadata, repository validation, and offline scorecard integrity. Runtime source release **0.18.382**. The HTTP `/api/ask` response adds only a SHA-256 of the exact validated submitted question (normalized whitespace), plus explicit no-proof flags for actual model input, first attempt and deployed build SHA. The existing Q1 capture CLI compares it to the registered question without exporting private prompt text. Invalid/contradictory fingerprints cannot be marked exact. No model/tool rounds added and no Hubitat/HA changes.

**Measured baseline:** Older first-response JSON has no API-sourced normalized question fingerprint; recorded Q1 source reviews could not authenticate their literal submitted question from the technical payload. **Installed v0.18.382 after-result: NOT MEASURED.** Matching a hash is *not* a human source grade, proof of first attempt, deployed commit identity, or live source completeness. Formal Q1 first-useful/grounded rates and Q2 Gemma/Claude comparison remain **not_measured**. This is improved diagnostic testability with offline tests, not evidence that any natural answer became better.

**Next single real Q1 acceptance:** After updating to 0.18.382 and selecting **New topic**, ask the unchanged registered legacy read-only question `What is the hub health status?` (case `broad_hub_health`). Paste the full HomeBrain answer plus complete Technical details JSON to the private chat. Verify `request_provenance.normalized_prompt_sha256` matches the frozen question, report observed run time and actual tool/model receipts, and then independently assess which health claims are supported by the returned sources. This one run will still not provide statistically meaningful percentages or an independently authenticated build SHA. Do not request any Internet-blocker-related action or replay already accepted device tests. Continue Q1 cross-domain first-answer capture and Q2 same-packet model review thereafter.

**Workstream freeze:** The user explicitly paused Internet-blocker research. Do not resume native delay writer, upstream developer requests or sandbox live tests without a new explicit request; disabled writer stays disabled.


## Original Q1 Answer Quality work resumed — blocker project PAUSED (2026-11-03)

**User direction:** Stop work on the delayed Internet-blocker and return to the **original HomeBrainOS answer-quality mission**. No new delayed-block development, native RM preflight questions, test device creation or upstream contribution until the user explicitly reopens that topic. The offline candidate remains disabled; no Hubitat/HA device or rule was changed. Resume **Q1 source/prompt provenance → same-evidence first-answer reviews → Q2 measured model A/B → Q3 publication/latency simplification**, not case-specific patches.

**Current reproducible inventory:** 40 curated *synthetic/anonymised* frozen offline inputs, 13 legacy targets, hash-pinned packet/export and private paired-review validator. This is **53 case definitions, not 53 actual answers**. Earlier real response reviews are not certified registered exact-first-attempt samples: actual HTTP-submitted prompt was unverified, deployed code SHA unauthenticated, evidence incomplete for some tasks and first-attempt status often unknown. No official ≥90% grounded, ≥80% first-useful or Claude-gap rate can be stated; `scripts/answer_quality_scorecard.py` still reports **not_measured** without independently reviewed outcomes.

**v0.18.382 candidate hypothesis:** Add to `/api/ask` a **privacy-minimal normalized-question SHA-256** of the actual validated request at the HTTP boundary. Update the existing Q1 metadata-only capture to compare that to the fixed legacy prompt and reject conflicts with separately supplied question text. This supports a source-grounded **request match**, not model-input delivery, proof of first attempt, deployed build SHA, independent source completeness or quality. No model calls or extra MCP reads; no output prose changes and no change to the write gate. Multiple offline tests cover privacy, missing/spoofed/contradictory digests, and offline-versus-live case separation. See [v0.18.382 hypothesis and rollback](../hubitat-mcp-ai/CHANGELOG-0.18.382.md) and [evaluation protocol](ANSWER-QUALITY-EVALUATION.md).

**Baseline / after:** Before: user-supplied diagnostic responses had no API-bound question fingerprint and formal source-graded exact-first-attempt sample count remains 0. After (on branch): code/tests, not installed live response. **Official Q1 quality gain NOT MEASURED**, correct-question attestation is an enabling condition, not a benchmark pass. CI/merge pending at this handoff until verified. Once a tested release is installed, sample one *unchanged registered read-only legacy question* with the full answer + Technical JSON, review actual source claims and claim gaps before assigning any score; do not ask to repeat previous Internet-blocker tests.


## Native Rule Machine parent identity — upstream class-projection contribution prepared, no live writes (2026-11-03)

**User approved proceeding with the native parent-identity blocker, not bypassing safety or modifying the live hub.** Current upstream `kingpanther13/Hubitat-local-MCP-server` source and Spock fixture were inspected: the native full `/installedapp/configure/json/<id>` may carry `parsed.app.appType.name/namespace`, but its public `hub_get_app_config` result drops them; cheap `summary=true` passes through `/installedapp/json/<id>` and on the user's installed read omitted the class; the type inventory may lack `systemAppTypes`. No existing source yet proves Rule Machine parent 169/type 18. **Do not invent or hardcode this join.**

**Upstream contribution blocked by permissions:** Attempts to create a branch and comment on [upstream issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) both returned **403 Resource not accessible by integration**. Developer was **not** notified. Prepared a source-backed, additive read-only native class projection and upstream test specification in [UPSTREAM-NATIVE-RM-PARENT-IDENTITY.md](UPSTREAM-NATIVE-RM-PARENT-IDENTITY.md) for an authorised maintainer to submit. It is NOT a merged upstream change or a fix already present in the user's installed server.

**Offline-only safety hardening:** the disabled native delay candidate now demands the *matching* `namespace="hubitat"` in addition to native type ID/name, `system`, `isBuiltIn`, `allowNewInstances`. Synthetic tests reject community, missing or blank namespace before backup/create/Run Actions. No add-on production import, version bump, Hubitat/HA writes, or test switch reuse. A separate exact read-only installed source must ultimately establish the parent class; then new disposable virtual-switch BAT still needs its own explicit scope/approval and recent backup. Q1/Q2 measured first-answer quality remains the primary roadmap; this is a source identity safety dependency only. PR CI/merge status must be checked, not assumed.


## v0.18.381 installed owned-device exact read PASS — independent native parent blocker remains (2026-11-03 16:58 UTC)

**Actual installed read-only acceptance:** User supplied HomeBrainOS `version=0.18.381`, `elapsed_ms=1321`, one `hub_read_devices → hub_list_devices` call (MCP HTTP 1257ms) and one local typed projection receipt (`tool_calls=2` including projection), no model rounds (`model=null`) and no modifying calls. Exact args: `scope="owned"`, `format="detailed"`, `cursor="0"`, `limit=20`. The source returned **1/1** MCP-owned device row across one page. Projection `evidence_kind=typed_owned_device_inventory`, `inventoryComplete=true`, `metadataComplete=true`, `virtualSwitchCount=1`, `error=null`, `investigation_coverage.domain=owned_virtual_device_inventory`, `questionResolved=true`, `metrics.outcome=success`. The visible answer correctly identified one previously existing, MCP-managed virtual switch; native `driverType` was unavailable but fallback native `driver=Virtual Switch` and `driverNamespace=hubitat` were reported. **Actual device ID/label intentionally not published in this repository** (private household inventory). No rule inventory or other rule operation ran. **Installed v0.18.381 source-route/answer acceptance PASS.** Do not change or repurpose this existing device for tests.

**Measured difference, not throughput benchmark:** Previous installed v0.18.380 failed request in **1.029s**, five unrelated rule-inventory receipts and **0 desired device reads**; v0.18.381 succeeded in **1.321s** with one remote desired device read + local projection. This is a request-completion and correct-source improvement, **not a measured latency reduction**. A repeated acceptance request is not an independent first-attempt Q1 benchmark success; official aggregate quality scores unchanged.

**Production writer remains blocked:** Parent candidate's app instance and appTypeId were previously observed, but no source-joined built-in Rule Machine `namespace/name` class proof. Upstream `hub_get_app_config(summary=true)` directly returns the platform's thin `/installedapp/json/<id>` projection without inventing the missing class. Its full configuration mode projects `appType.system/menu` only, so a general fallback cannot establish `namespace=hubitat,name=Rule Machine` on that source contract either. `hub_list_apps(scope="types")` may omit built-in entries when the upstream `/hub2/appsList.systemAppTypes` is unavailable. Therefore **no hardcoded parent, no MCP-created native BAT, no Internet blocking, no live writes**. [Updated BAT safety preflight](NATIVE-RM-DELAY-BAT-PREFLIGHT.md). The next capability dependency is an **authoritative, read-only native parent class identity surface from upstream** (or independently proven equivalent) and then separately approved harmless test with a **new** disposable switch, never the existing one. Do not repeat Rule 4259 or the owned-device inventory; resume the permanent Q1/Q2 answer-quality benchmark as the primary programme.


## v0.18.381 explicit MCP-owned device read general routing fix MERGED (2026-11-03)

**Verified release:** [PR #1354](https://github.com/ienam-smarthome/HomeBrainOS/pull/1354), exact tested head `fb1fb8c8f4e7945c774b1a67e34b97fef2b635f9` and merge SHA `667979f7294ce02d1a48737e15b1009484b8a4f6`, **6/6 CI jobs green**, **6,110 Python tests passed with two warnings**, add-on smoke, metadata and offline scorecard integrity green. Runtime source version **v0.18.381**. The strict explicit read path now routes `hub_list_devices(scope="owned",format="detailed")` straight to an authorized read-only gateway, with bounded pagination/ownership/completeness and source-scoped success/error presentation. Prohibitions like "do not call any Rule Machine operation" cannot select native rule inventory. No model planning added and no HA/Hubitat live changes.

**Observed before:** installed v0.18.380, same requested device-only read misrouted twice to Rule Machine inventory; latest 1.029s wall, 5 unrelated tool receipts, **0 hub_list_devices**, wrong answer, 0 paid/model rounds. **Installed after on v0.18.381: NOT MEASURED.** Do not call the known fail a genuine device-inventory absence, and do not score repeated same-task attempts as independent first answers. The next user action is **one identical read-only MCP-owned device-only prompt** after installing v0.18.381, returning the complete answer plus Technical details JSON. Acceptance: `hub_list_devices` under read-only `hub_read_devices` with scope=owned, format=detailed, bounded cursor pages; no rule-inventory calls; `investigation_coverage.domain=owned_virtual_device_inventory`, `questionResolved=true` only for source-complete reads. A source error must be shown as unresolved, not missing devices. Expected lower tool overhead is NOT an observed speed improvement yet.

**Critical independent blocker:** app candidate 169/type 18 STILL lacks an independently verified native Rule Machine built-in class join. Neither this device inventory nor the previous two successful Rule 4259 read sections proves that class. The triggerless delay writer stays offline-only, `NATIVE_DELAY_ENABLED=False`, and MCP-created BAT still needs separate explicit approval **after** valid native parent proof/other preflight. Do not repeat Rule 4259 actions/settings reads or apply the date-trigger upstream fix as a substitute for parent identity. Permanent Q1/Q2 answer-quality scorecard and natural reasoning remain primary, not incident-specific patch chasing. 


## Installed owned-device read misrouted to Rule Machine inventory — v0.18.381 candidate (2026-11-03 16:38 UTC)

**Real failed acceptance on v0.18.380:** The user ran the one-purpose read-only prompt for **MCP-owned virtual devices**, explicitly `hub_list_devices(scope="owned",format="detailed")` with a *prohibition* on Rule Machine calls. In **1.029s** HomeBrain instead issued four `hub_list_apps/hub_list_rules/hub_get_app_config(169)` reads plus typed Rule Machine inventory synthesis (five receipts); **zero `hub_list_devices`**, zero model rounds, no writes. It again reported candidate native parent 169/type 18 unverified and did not answer the owned inventory question. This is **second wrong-route observation**, not a failed virtual-device source query, and is not a new independent first attempt for the official benchmark. The correct device inventory is **unknown**, not empty.

**General production correction on candidate branch for v0.18.381:** explicit source-scoped, device-only `hub_list_devices` request takes priority over Rule Machine inventory even when the prohibition mentions Rule Machine; generic rule-inventory classifiers and finalizers do not intercept it. Strict owned/detailed args, bounded pagination, ownership/total consistency, source errors and typed requested-scope completion; no model needed. Synthetic first-answer and failure-path tests, no added writes or native parent assumptions. [Release hypothesis and measured baseline](../hubitat-mcp-ai/CHANGELOG-0.18.381.md). **CI/merge and installed after-result pending at time of this branch handoff.** Native Rule Machine parent proof remains missing; the production delayed writer is not activated. After a green release, a single repeat of the previously failed owned-device prompt with full Technical JSON is the only needed live check; do not ask for Rule 4259 again. Resume permanent Q1/Q2 evaluated answer-quality work after this general routing defect. 


## Native RM parent candidate 169/type 18 remains unverified; owned inventory was omitted (2026-11-03 16:22 UTC)

**Real installed read-only result (HomeBrainOS v0.18.380):** `hub_list_apps(scope=instances)`, `hub_list_apps(scope=types)`, `hub_list_rules`, `hub_get_app_config(appId=169,summary=true)`, and local typed inventory projection. Five tool calls, **1.057s wall**, model null, no writes; `investigation_coverage.domain=native_rule_inventory`, `questionResolved=false`, outcome `unresolved` correct. Source projection has candidate `appId=169`, `appTypeId=18`, `parents=[]`, `nativeRuleMachineTypeIds=[]`, `typeProofGap=no-matching-native-app-type-id`, summary `typeProofGap=native-app-summary-class-namespace-unavailable`. App/rule/type **returned lists were marked complete**, but the candidate's class cannot be proven by ID/name. The zero `(One-time ...)` suffix match is *not* a check of the offline candidate's `HB delay | ...` names. The prompt also requested `hub_list_devices(scope="owned",format="detailed")`; **no such tool call appears in receipts**, so owned virtual inventory is **not checked**, not absent.

**Upstream source confirmation:** `hub_list_apps(scope=types)` unions `/hub2/userAppTypes` (community) with `/hub2/appsList.systemAppTypes` (built-in only when returned). Incomplete built-in-class coverage can therefore occur despite a count-complete response. The summary endpoint lacks the typed class on this installed read. See [read-only BAT preflight](NATIVE-RM-DELAY-BAT-PREFLIGHT.md) for the upstream source scope, refusal and next exact single-object inventory prompt. Offline negative-control tests now check that complete but type-incomplete lists and matching community-class IDs **cannot promote parent 169**. This is a safety preflight validation, **not a verified answer-quality gain**. No production writer import/enablement or live Hubitat/HA mutation; `NATIVE_DELAY_ENABLED=False`. The next read-only test should ask only for owned virtual switch inventory; class proof will still require an independent typed native record or upstream support. Separately approved MCP-created BAT remains blocked. Permanent Q1/Q2 scorecard roadmap unchanged.


## Native delay settings/triggers read passed; unknown blanks preserved (2026-11-03 16:12 UTC)

**Installed v0.18.380 read-only evidence:** `hub_manage_native_rules_and_apps → hub_set_rule(operation="read",rule_id=4259,args.sections=["settings","triggers"])`, `success=true`, `sourceSuccess=true`, `projectionVerified=true`, `typed_native_rule_section`, one call (230ms MCP; 2,397ms end-to-end), zero model rounds and no writes. Returned prose lists 49 settings / 4 redacted or unsupported, `actType.1=delayActs`, `actSubType.1=getDelay`, `delayMinute.1=2`, `actType.2=switchActs`, `actSubType.2=getOnOffSwitch`, `onOff.2=false`, `onOffSwitch.2.device_ids=["7995"]`, and **zero returned triggers**. `delayHour.1`, `delaySecond.1`, `cancelAct.1`, `randomAct.1`, `uVar.1` are **blank**, not source-proven zero/false. The typed receipt retains only section success metadata, **not each raw setting row**, so do not exaggerate value-level independent validation or combine this and the earlier actions read as one same-snapshot native document. Read-only checkpoint complete; no repeated action/settings question needed.

**Offline-only general safety regression:** the candidate's existing fail-closed exact-setting verifier must never accept blank native number/bool readback as the requested zero/false. Synthetic regression cases now exercise those blanks and require no Run Actions after a mismatched read. Updated [preflight / isolated BAT guide](NATIVE-RM-DELAY-BAT-PREFLIGHT.md). **No runtime writer enabled, no HomeBrain version bump, no Hubitat/HA changes**. Guide/parent/type/backup/owned device preflight remains pending. The **next user HomeBrain prompt should focus on those missing read-only sources**; do not ask them for Rule 4259 again. Any MCP-created BAT rule/switch/ON/Run Actions still requires separate explicit approval. Permanent Q1/Q2 Answer Quality programme is not replaced by this safety capability work.


## Native delay BAT preflight — offline candidate protocol fix MERGED (2026-11-03)

**Merged and verified:** [PR #1350](https://github.com/ienam-smarthome/HomeBrainOS/pull/1350) from exact tested head `33492234e3d1b2374224ac86280d09c894ca2cd9`; **5/5 required CI jobs passed**, including **6,091 Python tests and two warnings**, full add-on smoke, metadata, validation and offline scorecard integrity. Merge SHA `08c7f318fa2827123f19b2c6800fad2ff4d2fd56`. Offline `scripts/native_rule_delay_candidate.py` now obtains **separate** installed section-guide acknowledgements for native `hub_set_rule` versus `hub_call_rule`/pause, with tests ensuring missing Run Actions guidance refuses before any mutation. The offline BAT [preflight and test runbook](NATIVE-RM-DELAY-BAT-PREFLIGHT.md) specifies remaining read-only inputs and a *separately authorized* MCP-owned Virtual Switch creation/ON, triggerless delay-OFF child creation/readback, single Run Actions, reported OFF verification, no automatic retries/cleanup, and no Internet hardware involvement. **Add-on remains v0.18.380**, no production imports/feature switch changes; `NATIVE_DELAY_ENABLED=False`. **No live Rule Machine/MCP mutation performed**.

**Next authorized step only:** User approved collecting read-only preflight and preparing the isolated BAT, not running it. Ask HomeBrain **once** for Rule 4259 native `sections=["settings","triggers"]` via `hub_set_rule(operation="read")`, with complete answer and Technical JSON; ordered `actions` are already live-verified, so do not repeat. Installed guidance/parent/backup/device scope may need later read-only confirmation. The user must separately authorize any new virtual device, ON state command, native rule creation or Run Actions; until then no writes, no cleanup, and no production Internet block. Current upstream date-field [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) remains open; the delay workaround does not depend on it if future native MCP creation/start BAT succeeds. This is safe capability research, **not a scored Answer Quality improvement**; permanent Q1/Q2 evaluation roadmap continues separately.


## Native delayed-block alternative — read-only preflight and isolated BAT preparation (2026-11-03)

**User explicitly approved only the read-only preflight and preparing a harmless MCP-created virtual-switch BAT for separate authorization.** Source review of upstream current `TOOL_GUIDE.md` and `libraries/mcp-native-documents-lib.groovy` confirms native Rule-5.1 `hub_set_rule(operation="create")` and `hub_call_rule(action="actions")` are documented operations; **this is not an installed hub write success**. Dated `atDate#` upstream [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) remains open and is not required for the triggerless delay alternative.

**Offline contract defect:** separate section-specific acknowledgements are required for `hub_set_rule` (`set_rule_reference`) and `hub_call_rule` / `hub_set_rule_paused` (`builtin_app_tools_rules`). The existing offline candidate only retrieved the first; an injected-transport-only correction plus fail-closed tests requires both before writes. **No production import, no HomeBrain add-on version change, `NATIVE_DELAY_ENABLED=False`, no Hubitat/HA live operations.** See [BAT preflight/runbook](NATIVE-RM-DELAY-BAT-PREFLIGHT.md) for exact read-only source requests, separate approval boundary, on-state initialisation, one-time start, partial/create-timeout handling, post-delay event checks and disabled cleanup. CI/PR/merge pending until checks verified.

**Source-complete state:** installed v0.18.380 previously verified actions-only rule 4259 read `getDelay` then `getOnOffSwitch`; earlier saved selector fields and manual OFF event exist. Typed **settings+triggers same-snapshot read**, installed guide/parent/backup/virtual target inventory, actual MCP creation/Run Actions, pending job attribution, and reboot survival remain **unverified**. Next user-only step is **one** safe `hub_set_rule(read,rule_id=4259,args.sections=["settings","triggers"])` with full answer and Technical JSON. Do not re-request actions or execute Run Actions. Production writer stays blocked until separately approved isolated BAT and integration safety gates; Answer Quality Q1/Q2 remains the primary development roadmap.


## v0.18.380 installed exact-native-actions acceptance PASS — close scoped read incident (2026-11-03)

**User-provided installed live capture (14:46:02 UTC):** add-on `version=0.18.380`, `elapsed_ms=1793`, `metrics.timings_ms.total=236`, one MCP call (`mcp=216 ms`, `mcp_http=215 ms`), **zero model rounds** (`model=null` and no model-round counter). Target `rule_id=4259`, gateway `hub_manage_native_rules_and_apps`, `hub_set_rule(operation="read", args={"sections":["actions"]})`; typed `evidence_kind=typed_native_rule_section`, `sourceSuccess=true`, `projectionVerified=true`, `success=true`, read effect, `mutates=false`. Ordered native rows: `{id:"1",method:"getDelay"}` then `{id:"2",method:"getOnOffSwitch"}`. The **visible answer** printed those two methods in the verified order, preserved the no-execution caveat and made no modifying calls. `investigation_coverage.domain=native_rule_section_read`, `status=requested-sections-verified`, `questionResolved=true`; `metrics.outcome=success`. **Scoped v0.18.380 installed acceptance PASS**, without implying complete native action-parameter verification or delayed Internet writer readiness.

**Matched user request, three actual builds — different routing, NOT controlled throughput A/B:** v0.18.378 22.202s / five free model rounds / six tools / no verified scoped action read; v0.18.379 1.914s / zero rounds / one tool / source read verified but user answer falsely unresolved; v0.18.380 1.793s / zero rounds / one tool / source-aligned successful answer. This is **one real repeated release acceptance case**, not three independent first attempts and not an eligible official aggregate 90%/80% score. Ordinary natural user queries, complex investigations, and model-vs-finaliser evidence-first answers remain unmeasured here. The UI displays two ordered list items both numbered “1.” due to paragraph breaks; cosmetic formatting does not invalidate source/coverage correctness and is not a reason for another incident-specific release.

**Next unfinished permanent roadmap milestone: Q1/Q2 frozen same-evidence first-answer baseline** (source-reviewed, denominator-based, across lighting/heating/telemetry/causality/control), then measured model reasoning A/B and publication simplification where justified. Do not ask again for rule 4259 actions or replay already submitted MQTT/lighting logs; do not reopen a timed Internet-block writer implementation without separate permission and harmless MCP-created test. Preserve no live Hubitat/HA changes and default read-only. No repo version change for this documentation-only completion.


## v0.18.380 native source-scoped publication fix MERGED (2026-11-03)

**Verified release:** [PR #1347](https://github.com/ienam-smarthome/HomeBrainOS/pull/1347), exact tested head `d0033634c951d05a2b7feecfc8093dae1938889c`, **6/6 required CI jobs green**, **6,088 Python tests passed with two warnings**, add-on smoke, metadata, validations and offline scorecard integrity green. Merge SHA `c47be6c73e90409a0f255bbe58e976f816ad6c1a`. Source version **v0.18.380**. The orchestrator and shared completion now use one strict receipt matcher for a requested native section instead of replacing a correct direct-read answer with unrelated whole-rule obligations; nonmatches are not admitted, source errors stay unresolved. No new model/MCP calls, no Rule Machine writer, no live changes.

**Measured before on installed v0.18.379:** 1.914s wall, 1 read MCP call (148ms), zero model rounds, source-verified ordered `getDelay` then `getOnOffSwitch`, but visible final answer incorrectly said the action order was unverified / unresolved; **retrieval PASS, first-answer publication FAIL**. **Installed v0.18.380 after-result remains NOT MEASURED**. One identical read-only HomeBrain prompt and full Technical JSON should verify whether the visible message actually lists both methods, `investigation_coverage.domain=native_rule_section_read`, `questionResolved=true`, `metrics.outcome=success`, 1 tool / 0 model rounds. This validates the requested actions section only, not action parameters, execution, other rule sections or Internet-block readiness. Official broad benchmark accuracy, first-attempt rate, matched A/B and Claude gap remain NOT MEASURED. **Then return to permanent Q1/Q2 frozen evaluation rather than more incident-specific changes.**


## v0.18.379 installed native actions read PASS; answer-publication contradiction (2026-11-03)

**New actual live acceptance:** User installed **v0.18.379**, repeated the identical explicit read-only prompt, and received a successful `typed_native_rule_section` receipt from `hub_manage_native_rules_and_apps → hub_set_rule(read)` with exact `args.sections=["actions"]`, `sourceSuccess=true`, `projectionVerified=true` and ordered `[{id:"1",method:"getDelay"},{id:"2",method:"getOnOffSwitch"}]`. One MCP tool call (148ms), zero model rounds, **1.914s wall**, no paid calls, no Hubitat/HA mutations. **Native read retrieval PASS.** This proves two ordered method names, not the native action parameters, full trigger/conditions, schedule execution, or physical effects.

**New answer quality defect:** The actual user-facing answer was rewritten as generic existing-rule verification, claiming ordered actions were not verified and showing `unresolved` / `questionResolved=false` despite the successful source-typed section projection. **Useful first answer FAIL** on this registered real request (one observed case, not official frozen benchmark percentage). Repo inspection identified broad `calibrate_existing_rule_verification` and shared completion as source-agnostic overwriters. **v0.18.380 candidate** adds a general source-scoped completion contract for any exact `hub_set_rule(read, sections)` with matching typed receipt; it preserves the verified direct-read answer and success for the requested section only, retaining unresolved/error for failed reads. No model rounds or writes added. [Release hypothesis](../hubitat-mcp-ai/CHANGELOG-0.18.380.md). CI/PR/merge and installed after-result PENDING. Maintain Answer Quality roadmap; after this bounded fix return to Q1/Q2 fixed-packet grading and source-attested model prose, not further case-specific patches.


## v0.18.379 exact-read natural-ID regression fix MERGED (2026-11-03)

**Release verified:** [PR #1345](https://github.com/ienam-smarthome/HomeBrainOS/pull/1345), exact tested head `9fefa0cbf777e94de009c99825a971f254363741`, **6/6 CI jobs green** across four workflows, **6,085 Python tests passed with two warnings**, add-on container smoke and metadata validation green. Merge commit `e1cea523232ca665c1921b963e8c9fa04cac7217`. Runtime version **v0.18.379**. The general intent-parser change admits natural `rule 4259` as well as `rule_id=4259` only inside an otherwise explicit validated `hub_set_rule operation=read sections` request, rejecting inconsistent exact IDs. No writer activation and no live Hubitat/HA mutation.

**Source-real before-result (installed v0.18.378):** 22.202s wall, 5 Gemma Cloud free rounds, 6 tool calls, 0 paid, all-section read marked unsuccessful, action list not returned, exact direct-read route not selected. **After-result on installed v0.18.379: NOT MEASURED.** Ask for one read-only identical user prompt and complete technical JSON only after the user confirms installed v0.18.379. Acceptance requires one `typed_native_rule_section` receipt containing gateway, exact `requestedSections=["actions"]`, source-vs-projection success/failure and either true ordered action IDs/value.method or bounded raw error code/message; report wall/provider/rounds/tools. Do not assume remote action tree shape is valid until source verified or enable disabled delay writer. Official frozen-case A/B, 90%/80% quality and Claude comparison remain NOT MEASURED. Return to measured benchmark Q1/Q2 after this release's single acceptance check.


## v0.18.378 live explicit-read failure; v0.18.379 parser repair awaiting CI (2026-11-03)

**Real installed acceptance failure:** User repeated the exact direct-read prompt `Read existing Rule Machine rule 4259 using hub_set_rule with operation="read" and args={"sections":["actions"]}` on reported add-on v0.18.378. Technical JSON recorded a broad host `hub_set_rule(operation=read,rule_id=4259)` **without requested sections**, `success:false` all-section projection, five Free Gemma rounds, six tools, 22.202 seconds wall / 18.358 seconds provider / 0 paid, and generic partial configuration response. The direct `typed_native_rule_section` receipt is absent. Stored delayMinute.1=2, onOff.2=false and target device 7995 are verified only as independent saved settings, not action order. No modifying hub calls. **v0.18.378 live acceptance FAIL** for precise read intent; upstream error and native action tree remain unknown.

**Root cause in 0.18.378 parser:** `parse_explicit_native_read` required the literal token `rule_id=4259`. The documented acceptance prompt used natural-language `rule 4259`, so it fell through to existing all-section prefetch and model planner. **v0.18.379 branch** extends only exact explicit read intent matching to either spelling, rejects conflicting IDs, and replays the actual prompt plus no-write checks in offline regression tests. Release hypothesis and rollback in [0.18.379 release notes](../hubitat-mcp-ai/CHANGELOG-0.18.379.md). No writer integration or live Hubitat/HA mutations. **CI/merge and installed after-result pending**; official first-attempt quality, source validity and latency changes cannot yet be inferred.


## Native Rule Machine exact-read retrieval fix — v0.18.378 candidate (2026-11-03)

**Latest live failure at installed v0.18.377:** User pasted the same direct read-only prompt requesting `hub_set_rule operation=read, rule_id=4259, args.sections=['actions']`. The add-on returned the same generic rule verification text in **15.702s, 5 Gemma Cloud free model rounds, 6 tool calls**. Host prefetch nevertheless tried `hub_set_rule(read)` with **no `args.sections`**, labeled its result `success:false` under its strict **all-section document projector**, and published only `Native rule document unreadable or incomplete` with no raw source error. `read_only_model_write_blocked=1` also occurred but is not linked to a particular call in public diagnostics. Typed `hub_get_app_config` shows `delayMinute.1=2`, `onOff.2=false`, `onOffSwitch.2.deviceIds=['7995']`; no action-order read success. Upstream implementation supports a one-section native document read; failure cause is NOT established. Repeating only the wording of the read prompt is not productive.

**Implementing** `v0.18.378` as a general **explicit native read retrieval** route in `native_rule_document_source.py`, called ahead of model planning for a syntactically specified `hub_set_rule operation=read + one rule_id + allowed sections`. It uses only the installed gateway and the typed read effect classifier. This issues one bounded read with the **exact requested sections**, renders native action ID/method order only when directly present, never promotes a partial settings read to executable-action proof, and returns a redacted **actual MCP error code/message or source-verified projection failure** without losing distinctions under broad all-or-nothing review. Adds isolated synthetic success/failure/redaction/no-write tests. No live user rule or device changed. This changes production **read-only behavior**; `scripts/native_rule_delay_candidate.py` and real timed Internet blocks remain DISABLED/unverified.

**Verified release:** [PR #1343](https://github.com/ienam-smarthome/HomeBrainOS/pull/1343) merged from exact tested head `5f55d09e169a6dda5c383fe64dc42775732df74e`: **6/6 CI checks green**, **6,084 Python tests passed with 2 warnings**, add-on smoke, metadata and validations green. Merge SHA `9ab3711be06925269dc2606d22e8e0762a685c60`. This is a production read-only routing/response change; it does not enable a native delayed-block writer. See [release hypothesis](../hubitat-mcp-ai/CHANGELOG-0.18.378.md). The user must first install v0.18.378; then repeat one explicit read-only native actions prompt to measure actual source and latency. Evaluate receipt `typed_native_rule_section`, gateway, operation/sections, outcome, source-vs-projection distinction, ordered methods or raw error, model rounds, MCP calls and latency; **do not claim live success before that capture**. Further source-error diagnosis or MCP authoring will depend on the returned result. No paid model tests or Hubitat/HA writes authorized.

## Native delay readback source-contract correction — offline-only, 2026-11-03

**Live follow-up:** HomeBrain v0.18.377 ran a read-only check against the existing manually tested Rule Machine rule and verified saved `delayMinute.1=2`, `onOff.2=false`, `onOffSwitch.2.deviceIds=["7995"]`, `paused=false`, `stopped=false`, `broken=false`. The attempted `hub_set_rule(operation="read",rule_id=4259)` receipt was **success:false**, with no raw error in the diagnostic output. Its call omitted explicit sections, but upstream `toolGetRuleDocument` defaults missing sections to all; **do not assert this omission caused failure**. Counter `read_only_model_write_blocked=1` does not identify which attempt was blocked. Model got 7 rounds/8 calls, wall 31.124s, free Gemma, unresolved. Native actions/trigger identity and readback remain unverified.

**Generalizable offline harness defect:** The native server's actual document read shape for actions is ordered `[{id:"1",value:{method:"getDelay",...}},...]`, not `[{id:1,subtype:"getDelay"}]` as the offline delay writer's fake-hub fixture asserted. Test-only PR changes the candidate verifier and simulator to match published upstream source and rejects the inaccurate subtype-only shape; no add-on imports/changes, no new live calls. See [native delay review](NATIVE-RM-DELAY-REVIEW.md). The offline candidate stays **DISABLED**. Next user-only read is one explicitly scoped `hub_set_rule(operation="read",rule_id=4259,args={sections:["actions"]})`, returning **raw error** if it fails; then single-section settings and triggers if available. Do not repeat the working Run Actions, change the rule, or enable real Internet-control writes.

## Live manual Rule Machine delay BAT — actual OFF records, native writer still unverified (2026-11-03)

**Latest evidence:** A manually created trigger-less Rule Machine test with exactly two intended actions, `Delay 0:02:00` then `Off: Virtual Test Switch`, successfully produced a Hubitat **switch=off state report at 12:25:27.796** and **command-off at 12:25:27.798**, **both bearing `producedBy` the same test Rule Machine app**. The second HomeBrainOS v0.18.377 diagnostic JSON contains these source event rows and reports the app logged `Delay Over 12:25:27.772` / OFF action `12:25:27.781`. App-log row text is not included in the exposed diagnostic receipt; Hubitat UI originally showed a delay log at `12:22:37.750`, whereas model's later summary says `12:23:27.750` (50-second difference, cause unverified). Switch report 2ms before command record: source timestamp ordering is not proof of physical command-first sequence. **Manual delay/outcome PASS**; no actual Internet change occurred. No live Hubitat/HA changes by the development agent.

**Model result:** Second read 33.382s wall, 7 model rounds/7 tool calls, `gemma4:31b` free, 0 paid; first failed read 38.818s/9 rounds/13 tools. Differing source access makes comparison *not controlled*. Second tool read resolved the virtual switch and read app-linked `switch=off` and `command-off` events; first read failed device discovery and wrongly concluded the device **does not exist**. Upstream MCP device allowlist applies to manually created virtual devices; authorization change is plausible **not confirmed**. A failed MCP device read cannot establish that a device does not exist. Health read at 12:30 lists no `scheduledJobCount` in public receipt; model's value 0 is not independently shown and post-completion 0 is not contradictory.

**Immediate next milestone:** **Read-only** `hub_set_rule(operation="read",rule_id=<existing test rule>,args={sections:["settings","actions","triggers"]})` via installed server's verified read route, to capture *typed native action field names/values/order and trigger absence*. Prior `hub_get_app_config` page reads do not attest typed native `actions` or their order; in summary `orderedActionsValidated=false`. Do NOT activate `scripts/native_rule_delay_candidate.py`, change version, write backup, run existing rule again or enable cleanup without separately approved harmless **MCP-created** test and read-after-write confirmation. Reboot survival and scheduled-job count *while pending* remain unverified. Exact evidence/audit limitations in [NATIVE-RM-DELAY-REVIEW.md](NATIVE-RM-DELAY-REVIEW.md). Real benefit: manual RM delay established, **native MCP writer NOT TESTED**. No claims of Internet block functionality yet.

## Native RM delayed actions — alternative to unsupported dated triggers, AUDIT ONLY (2026-11-03)

**Correct upstream issue:** [Hubitat-local-MCP-server #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575), not unrelated #320. Live MCP 5.1.1 native form `atDate1` is typed `date` `supported:false`, and adding `atDate#` fails with `Unsupported native setting type`. This establishes why native date-based one-shot triggers cannot currently be created; issue is open. The user supplied two Python files for a *triggerless* delay action followed by switch off/on, started via `hub_call_rule(action=actions)`. The original **13/13 synthetic tests pass** but do not establish a real scheduled job, physical device effect, exact deadline or reboot survival.

**Independent source/sample review found seven classes of problems:** source due time floored before the requested duration; duplicate exact-name request reruns the old rule's actions; create timeout may start an unconfirmed partial child; unsuccessful Run Actions response ignored; readback permits omitted trigger collection and unreviewed extra actions; cleanup may delete pending jobs based on just the label/approximate clock; cursored typed Rule Machine parent identity and authoritative backup/duplicate inventories incomplete. The user already has unrelated prior 0.18.377 *dated-trigger* refusal and cleanup safeguards, which must not be removed.

**Verified offline review merge:** [PR #1339](https://github.com/ienam-smarthome/HomeBrainOS/pull/1339), exact tested head `114efb1a0598c62cb759f60e4f75b03ee4201621`, **6/6 CI checks green**, **6,066 Python tests passed, 2 warnings** (including new synthetic adversarial cases), add-on smoke, metadata, offline scorecard and both validate jobs passed. Merge SHA `75aed5e9555200ff38e77895df003d3778f6af7f`. Adds `scripts/native_rule_delay_candidate.py` plus `tests/test_native_rule_delay_candidate.py`, source-reviewed in [native delay research note](NATIVE-RM-DELAY-REVIEW.md). This is intentionally **offline, NOT runtime-integrated**: no imports in the add-on, unchanged add-on version 0.18.377, `NATIVE_DELAY_ENABLED=False`, no async confirmation adapter, no after-fire cleanup. Candidate requires explicit test opt-in/approval and refuses missing/ambiguous evidence. Synthetic tests are NOT a live scheduling success. Native actions readback shape, actual Run Actions delay scheduling, reboot persistence, job attribution and physical Internet effect remain unverified. `scheduledJobCount>0` alone does not prove the requested timer's execution; cleanup remains disabled. **Delayed Internet control remains UNAVAILABLE on the installed native server** pending safe end-to-end evidence and separately approved live test.

**Next real milestone:** after explicit separate permission, harmless virtual switch 1–2 minute BAT with fresh backup, one created test rule and readback, one Run Actions, observed pending timer and final reported switch state; reboot/cleanup require separate approval. Only then decide whether to wire a persisted, confirmed native delay adapter into HomeBrainOS, or await upstream native `date` support. No live Hubitat/HA changes or paid model calls made in this audit.

## Native timed Internet block — v0.18.377 safety release MERGED, writer still BLOCKED (2026-11-03)

**User report:** Delayed/scheduled Internet-control writes failed under the new native Rule Machine API. Source proposal suggests native dated trigger fields, native parent verification, live probe rule and a fallback scheduler. Current runtime `rule_authoring_service.py` still compiles legacy `addTrigger/addAction`; its `rule_writer_contract.py` correctly detects the new `operation=create` guide and refuses before a write. The upstream time/date field has *not been read back from a real dated native one-time rule*; the repo's offline `scripts/native_one_time_rule_compiler.py` explicitly cannot authorize writes, and existing parent type list could omit system types. **Do not claim scheduled blocking works or that native parent ID 169 is independently verified from the user's newly supplied text.** The proposed write payload and date field are not yet proven by upstream schema or live readback. User has not specifically authorized creating/deleting the probe rule, so **no hub writes or probe**.

**Current safe coding candidate:** v0.18.377 changes the native one-shot refusal from generic "Couldn't schedule" to **`native_oneshot_date_field_unverified`**, retains `rm_contract_changed` for other native/legacy mismatch; adds pure typed dated-versus-undated settings comparison under a hard-off native writer gate; rounds relative schedules up after real elapsed UTC time; rejects one-time clock times less than or equal to 60 seconds away, DST gaps and repeated local hours; gives newly generated one-shots the `HB one-shot |` prefix and prevents the built-in destructive cleanup from matching suffix-only historical/user-created rules. Existing legacy suffix-only rules require manual cleanup review and are not auto-deleted. Runtime native creation is still BLOCKED, confirmation/backup/readback lifecycle and local fallback remain UNIMPLEMENTED, and a user-approved probe is needed for date field/value proof. See [release hypothesis/safety/limitations](../hubitat-mcp-ai/CHANGELOG-0.18.377.md).

**Merged implementation and real limits:** [PR #1337](https://github.com/ienam-smarthome/HomeBrainOS/pull/1337) tested exact head `bbf399abb914084fa122f1d0d4f0995ecb97772d`, **8/8 exact-head CI checks green**, **6,039 Python tests passed with two warnings**, full add-on smoke, metadata, scorecard and release gates green; merge SHA `edcef300e3730cb2a42fd200dfa47c573ba466ac`. This verifies only the synthetic date form difference detector, specific native refusal, clock rounding/gap rejection and new ownership-safe cleanup filter. It does **NOT** enable delayed Internet blocking under native Rule Machine; `NATIVE_ONESHOT_ENABLED=False`. Old suffix-only rules are intentionally excluded from automatic cleanup and require manual review. No Cloud model usage or live Hubitat/HA operations. Actual scheduled-control execution, exact date field, last-packet/target reachability, latency and after-fire cleanup remain **NOT MEASURED**. Next: the user can manually create/read/delete one harmless dated `ZZ probe` after a fresh backup, using the actual advertised native read contract; return redacted typed settings and an undated comparison. The user has not authorized HomeBrain to create or delete that rule. Only then implement opt-in native backup, confirmation, idempotent create/readback/verification and after-fire lifecycle, or independently authorized persisted local-scheduler fallback. No blind retry after create timeout.

## Q3 live v0.18.375 after-result — concise grounding PASS, round reduction NOT ACHIEVED; v0.18.376 post-read gate MERGED (2026-11-03)

**Actual installed first answer:** The registered read-only `device_mqtt_conflict` question on **v0.18.375**, Gemma4:31b via ollama-cloud, returned **39,649 ms wall**, **34,027 ms provider**, 8 model rounds, 7 tool calls, zero paid; final `outcome=unresolved`. The user-facing answer clearly separates saved `healthStatus=offline` and `mqttStatus=connected` from unverified physical/transport state and says the outage cause is unresolved. One source-reviewed causal calibration **PASS**; root-cause resolution **not achieved**, not proof of model semantic competence. `answerPublicationDecision.mode=concise`, `replacementPerformed=true`, `modelFirstRejection=material-uncertainty-omitted`, `rootCauseVerified=false`. The host source-typed publisher, not the raw Gemma draft, made the answer acceptable. 16 source-reported, 16 retained, `truncated=false`; this **does not test the new v0.18.375 partial-history-specific brevity branch**. The installed finalization still had `causal_read_round_budget_exhausted=1` and **no `telemetry_sufficiency_stop`**, with two source checkpoints and a successful device-scoped log and host-late device configuration read. Individual source log texts and true physical last packet not verified.

**Three live rounds (different source packets; not controlled A/B):** v0.18.373 57.559 s/8 rounds/9 tools (unsupported definitive cause FAIL); v0.18.374 44.647 s/8 rounds/8 tools (grounded but detailed PASS); v0.18.375 39.649 s/8 rounds/7 tools (grounded and concise PASS). No repeatable latency effect, no matched evidence semantic model A/B, no aggregate 90/80% score can be inferred. Model round reduction stayed at **zero** across these samples, though wall time was lower.

**Q3 general fix candidate v0.18.376:** The orchestrator's bounded single-target telemetry sufficiency stop was evaluated only after a **no-tool model reply**, not after a successful tool round that first fulfilled the same source contract. Evaluate the **identical** source-scope and checkpoint rule immediately after an actual *new* successful nonmutating read receipt; avoid a further planning turn if source-sufficient, but still use the existing final source completion and safe publication. No new model/MCP calls, no device writes. Offline cross-domain tests and CI must establish new-success-vs-duplicate, failed read, mutation, target mismatch, source incompleteness and multi-target exclusion. [Release rationale, risks and rollback](../hubitat-mcp-ai/CHANGELOG-0.18.376.md).

**Merged proof:** [PR #1335](https://github.com/ienam-smarthome/HomeBrainOS/pull/1335), tested exact head `c68d2fbef3e8afee411af1c6d2e89176fe87c15c`, **8/8 exact-head CI checks green**, **6,020 Python tests passed with 2 warnings**, add-on smoke, metadata, offline scorecard, tests and both release gate validation jobs passed. Merge SHA `0c1d5ced5b2ff58bfa8531dba5cdc781014cf640`. Code executes the existing target-scoped telemetry sufficiency check immediately after a successful nonmutating tool round with **at least one new successful read receipt**, rather than only when the model first voluntarily stops asking tools. It does not confirm packet freshness or upstream cause; model-first drafts remain subject to existing full final verification. **Installed v0.18.376 after-result remains NOT MEASURED**, with no confirmed repeatable model-round or wall-time saving. **Next priority: controlled matched-evidence model reasoning A/B** using the frozen cross-domain Q2 sample, not another incident-specific patch. Do not request repeated tests of the same device unless required for an explicit before/after and budget is acceptable; broader status/lighting/heating/causal first-attempt quality remains unmeasured. No Hubitat/HA or add-on settings changed by code development.

## Q2 v0.18.374 installed causal-calibration PASS; Q3 partial-telemetry concise v0.18.375 MERGED — 2026-11-03

**Source-real first-response evidence:** User supplied a fresh installed **v0.18.374** `device_mqtt_conflict` complete response and Technical JSON: **Gemma4:31b / ollama-cloud**, **8 free rounds, 0 paid, 8 tool calls**, **44,647 ms wall**, **33,685 ms provider**, **5,066 ms aggregate MCP HTTP**, **1,898 ms MCP**, final `outcome=unresolved`. Previously installed v0.18.373 was **57,559 ms wall / 51,182 ms provider / 8 rounds / 9 calls**. These are **one run each with changing evidence, not a paired latency benchmark**; percentage improvements are descriptive, not repeatable speed-up proof.

**Quality after:** v0.18.374 now includes `normalizedDeviceHistory` with **17 source-reported, 16 inspected, 1 explicitly unshown**; `joinedDerivedHistory=true`, `truncated=true`, `sourceIntegrityVerified=false`; `answerPublicationDecision.strategy=source-typed-evidence`, `mode=evidence-depth-required`, `modelProseCertified=false`; `publicationBoundaryShadow.replacementPerformed=true`. Its natural answer does **NOT** assert a confirmed ghost session or physical telemetry cessation and states source clock conflict and unknown cause. One-case **causal calibration PASS** versus v0.18.373 **FAIL**, no physical root cause identified. First-answer usefulness is **partial**: accurate status/next read-only check, but overly long and does not resolve the physical cause. One-case truthful evidence coverage improved, population-level factual grounding and Claude comparison **NOT MEASURED**. Source packets differ; semantic A/B control still absent. All actions read-only.

**Q3 code candidate 0.18.375:** Source-count-matched **truncated** event packets were wrongly excluded from existing bounded single-target telemetry sufficiency logic, causing extra recovery opportunities after scoped reads/checkpoints, even though the source-typed publisher can disclose unknown rows without guessing. The detailed publisher also forced full report whenever `truncated=true`, despite concise renderer displaying 17/16/1 caveat. Make readiness admit only independently paired explicitly counted partials following targeted status/history/scoped log and discriminator source/checkpoint, and select concise publication only for count-attested partials **with no positive command/watched watchdog timeline**. Full user report and any ambiguous truncation remain detailed. No extra model/MCP rounds, write permissions or network calls. Cross-domain negative control tests to guard source identity, window, source counts, log, command-path and full detail. See [release hypothesis, expected metrics, risk, rollback](../hubitat-mcp-ai/CHANGELOG-0.18.375.md).

**Verified merged implementation:** [PR #1333](https://github.com/ienam-smarthome/HomeBrainOS/pull/1333), exact tested head `db4bf9fe1d3fd6d3fa7f22815110b0d139314fdb`, **7/7 CI green**, **6,016 Python tests passed, two warnings**, add-on smoke, metadata validation, offline scorecard, `test` and both `validate` jobs green. Merge SHA `90901a54cadbb6d75b3a237d1129bf18ca4f80b8`; source-backed bounded-telemetry stop and concise answer selection are now in runtime add-on metadata **v0.18.375**. Cross-domain synthetic fixtures verify selected positive and negative cases, but this is not a recorded live answer-quality or latency effect. **Installed v0.18.375 after-result remains NOT MEASURED.** Next: ask for only one *new* read-only first answer + full JSON after user's normal add-on upgrade; verify `telemetry_sufficiency_stop` / round counts, answer publication mode, required uncertainty, and elapsed wall/provider time. The independently source-verified v0.18.374 causal-calibration PASS is one case, not a general correctness percentage. Keep permanent Q0→Q4 charter and upstream Rule Machine task independently outstanding.

## Q2 installed v0.18.373 first-answer FAIL; general partial-history repair v0.18.374 MERGED (2026-11-03)

**Actual first answer and exact installed version from supplied Technical JSON:** Registered read-only `device_mqtt_conflict` question, **v0.18.373**, Gemma4:31b through `ollama-cloud`, **8 free model rounds / 0 paid**, **9 tool calls**, **57,559 ms wall**, **51,182 ms provider**, **4,698 ms MCP HTTP**, **1,995 ms MCP**, 1 shared completion marked partial, final `outcome=unresolved`. User-visible answer definitively asserted device-level telemetry failure and a “ghost connection” root cause; `rootCauseVerified=false`, `questionResolved=false`, and **3/3 unverified hypothesis discriminators** contradict that certainty. Thus this one first answer is **causal-grounding FAIL** and not a confirmed cause, despite useful recorded-state evidence. 57.6s also misses the preferred 45s investigation target. The timestamps `lastSeen` (22+ days) and `dataAgeSeconds` (45.1h) disagree; a 24h truncated event page contains driver-reported health transitions, not verified physical packets. Logs were queried successfully, but the user-provided public Technical JSON does **not** expose individual source log rows, so specific claimed log texts cannot be independently source-audited from this trace. No write operations or additional cloud spend.

**Source-path defect found on actual metadata, independently of model reasoning:** successful targeted native history said `19 device events`; immediately derived `homebrain_device_history` retained **16**, explicitly `observedEventsTruncated=true`, `sourceEventCount=19`, `analysisEventCount=19`. `typed_device_history_evidence._join_derived_event_rows` previously refused any `len(observedEvents) != native summary count`, yielding `normalized=None`, so its source-backed answer was not selected and free-form model cause remained prominent. Missing `normalizedDeviceHistory` and `answerPublicationDecision` in the live response are consistent with this code path; no internal model draft was captured, so exact route-level responsibility for all prose is unverified.

**Merged general correction v0.18.374:** Admit a derived subset only when *explicitly truncated*, both derived counts equal native source count, time-scope, target and unique matching receipt are verified; retain exactly the observed rows and disclose total-vs-retained discrepancy. This is not another MQTT-specific wording filter. Add cross-domain synthetic positives and wrong-ID/window/time/count negatives and an integrated assertion that unsupported model cause is discarded when the source-typed boundary becomes available. No new model calls, reads or write/control capabilities. [Change hypothesis, risk, rollback, measurement](../hubitat-mcp-ai/CHANGELOG-0.18.374.md).

**Before/after:** Before on one real v0.18.373 read = 19 reported / 16 observed, publisher absent, causal-grounding **FAIL**, 57.559s latency. After **7/7 exact-head CI green** on [PR #1331](https://github.com/ienam-smarthome/HomeBrainOS/pull/1331), tested head `a65eada36edf59c13fd3496fa889083fd87faa58`, merge `f6f2b54e30b018000d16cfab4a0a1cd8bdaba339`; **6,011 Python tests passed with two warnings**, add-on smoke, metadata, scorecard and validation checks passed. Offline fixture now admits 16/19 source-declared rows and exposes three as unshown, plus cross-domain fail-closed checks. **This proves source-admission behavior, not actual model factual accuracy.** The installed after-result, Q2 Gemma-versus-other-model semantic comparison, quality sample proportions and improved latency remain **NOT MEASURED**. Next: after normal user upgrade, obtain one new first-attempt read-only `device_mqtt_conflict` answer and full JSON, check `normalizedDeviceHistory` / `answerPublicationDecision`, and grade the cause and time without inventing comparison percentages. No physical device outcome or live environment mutation claimed.

## Q2 next generalisable source-role milestone — v0.18.373 MERGED (2026-11-03)

**Verified merged result:** [PR #1329](https://github.com/ienam-smarthome/HomeBrainOS/pull/1329) from exact tested head `ef389922a8e6ab18ab009f90caba09bb1cf163e8`; 8/8 CI green, 6,007 Python tests passed with two warnings, add-on container smoke, offline scorecard and repository validation green. Merge commit `03a0bc2b57ca3ae08aabd29fd74feceb00bfa98e`; runtime package metadata now **0.18.373**. No installed user result or live Hubitat/HA changes.\n\n**Starting main:** `901bffd658a60ffd9d0a84dd8de5da25ec32d068`. This branch addresses a confirmed general native MCP evidence-ingestion gap, **not** the upstream Rule Machine one-time writer blocker and not a new lighting-specific wording patch. The existing `causal_initiator_provenance_guard.build_state_report_provenance` accepted deterministic `observedEvents/boundaryEvents`, but excluded successful device-scoped native `hub_list_device_events.details.events` and typed `producedBy={id,type:"app"}` command producers. The model's source-role briefing and final evidence guard could therefore receive zero reported-state/command roles even when those native rows were present.

**Candidate:** Admit native rows only after the existing independent successful read, live-claim, exact device-ID and nonmutating guards. Require role-typed actor IDs and reject conflicting/untyped producer identities. Preserve separate recorded-command, reporting-device and notified-listener edges; do not certify causation, physical execution or external origin. Tests include cross-domain anonymised examples, source-scope rejection and integrated synthesis-validator coverage. No extra reads, rounds or device writes; production package candidate **0.18.373**. Rollback is the source-role normalizer/row fallback and release metadata.

**Bounded offline measurement:** Previous code recognized **0 source roles** from a synthetic native `details.events` packet, even with one command and one switch report; new tests expect **1 command, 1 state and 1 listener** from typed, scoped rows. This is evidence-ingestion coverage, **NOT** a measured improvement in actual AI answer factual accuracy, usefulness, naturalness or latency. The v0.18.371 installed Gemma external-origin failure and v0.18.372 pending live MQTT after-result remain separate observations. No claim that v0.18.373 passes actual first-answer benchmarks or solves arbitrary unverified prose. All exact-head CI checks and the merge were verified. User-installed v0.18.373 real first-answer outcomes remain **NOT MEASURED**; do not equate source-ingestion test success with factual answer quality.

**Next real evaluation:** Once the newest add-on is installed with the user's normal permission, run the registered read-only `device_mqtt_conflict` prompt once and capture its full answer + Technical JSON or request-ID-matched failure logs. Then review the first attempt under Q2; compare only identical frozen evidence packets across providers/versions. The formal first-useful/grounding/model A/B denominators remain **NOT MEASURED**. Do not ask for a previously supplied first answer or make native Rule Machine writes.

## Q2 second live test — 180s MQTT timeout; v0.18.372 bounded read fix MERGED (2026-11-03)

**Verified merge and CI:** [PR #1327](https://github.com/ienam-smarthome/HomeBrainOS/pull/1327) exact tested head `bfc02e8662b31db99f46e64f44d82878b230ae53`, merge commit `d96d22241ce6b4eb9dc044867e4cfcce759ff819`; **8/8 CI green**, **6,000 Python tests passed, two warnings**, add-on smoke and offline scorecard validation green. Runtime code and package metadata now contain **v0.18.372**. There is **no evidence it is installed in the user's Home Assistant yet**; post-upgrade live first-answer success/latency **NOT MEASURED**. The prior 180s request's causal source hang remains unknown without the add-on Logs. Last complete installed Q2 Gemma lighting answer remains v0.18.371. No MCP server upstream Rule Machine identity or one-time dated rule changes.

**Observed first-attempt failure:** User ran the registered `device_mqtt_conflict` question in the installed HomeBrain UI with the free Gemma default. HomeBrain returned `success=false, route=error` at the **180s investigation deadline**, stuck in **Executing tool calls (round 2/6)**, reporting **no verified read-only results**. Screenshot shows "MCP online" and "Ollama ready", but these only describe superficial service status; neither proves the individual tool or model completed. No complete per-request logs or request ID were present. **MQTT explanation quality could not be scored: NO ANSWER**. First-attempt service usefulness **FAIL (timeout)**, latency **FAIL (180s vs <45s goal)**, causal/MQTT factual grounding **NOT MEASURED**, no observed writes.

**Repo-confirmed mechanism / bounded hypothesis:** Coordinator limits the full investigation to 180s and logs a generated request ID, but the HTTP 504 omits that ID even while telling user to search logs. In `tool_executor.py` a model-emitted read may wait in a local handler or MCP call queue beyond an independent per-model-read budget; this can consume the whole coordinator deadline. **Which exact tool hung, its transport, and its real cause remain UNVERIFIED**. This is a general deadline reliability gap across domains, not evidence of MQTT device failure.

**Merged v0.18.372 behavior:** Keep overall 180s ceiling and all write/confirmation boundaries intact; bound each *model-selected read* handler/MCP await to 30s, cancel it and record an explicit failed nonclaim receipt rather than fabricating a healthy/absent state. Count `model_read_timeout`. Leave host-originated reads and all writes outside this per-model-read guard. Include the existing request ID in no-evidence 504 diagnostics for log correlation. This does not guarantee the entire investigation finishes in 30s or identify the actual user's blocked operation. [Release proof notes](../hubitat-mcp-ai/CHANGELOG-0.18.372.md). No live Hubitat/HA changes and no cloud calls.

**Measurement:** One source-real installed baseline = **180s/no verified source/no answer**. After deployment to user's actual add-on **NOT MEASURED**. Mocked tests can establish timeout and cancellation mechanics only; actual source root cause and whether the fixed code path covers it require add-on request logs and a later *one-time* controlled read-only retest. Do not increase `investigation_deadline_seconds` and do not interpret no returned rows as physical offline proof. The first Q2 light investigation remains a separate source-review causal-overclaim FAIL; one-time Rule Machine native creation remains blocked by upstream class/dated trigger contract.

**Next action after merged release:** Install/upgrade the add-on only with the user's normal permission. Review add-on Logs using the displayed request ID if it still fails. Do not treat a normal HomeBrain chatbot request as safe to auto-retry, and do not run a write or consume cloud quota just to reproduce a timeout. Return to independently sourced MQTT answer-quality analysis once an actual answer exists.


## Q2 first real configured-Gemma causal answer: definitive external-origin overclaim (2026-11-02; review candidate)

**One real first answer, source-bounded qualitative review:** User supplied the previously requested registered `causal_light2_off` investigation's full response and Technical JSON, reporting add-on **v0.18.371**, **Gemma4:31b / ollama-cloud**, **8 free model rounds**, **16 read-only tool calls**, **37.474s wall** (**31.104s provider**), **2 synthesis validation issues**, **1 failed repair** and **1 causal coverage confidence alignment**. The exact initial provider payload and deployed Git SHA cannot be independently verified. No Hubitat/HA writes.

**Verified failure class:** The latest OFF state report was produced by a Matter bridge, and the returned command-OFF rows did not identify a matched issuer at that boundary; historical completeness was not proven. `triggered[]` are downstream listeners. Nevertheless, the final natural answer **concluded an external cause** and stated the bridge's `physical`-classified state report confirmed Hubitat merely observed the event. This falsely promotes reporting provenance and a bounded lack of command evidence into external causation. Its own `rootCauseVerified=false`, `questionResolved=false` and three unverified hypothesis discriminators contradict that conclusion. Historical sensor archive was collector-reception-only; focal app-decision logs were not verified. This is one **source-reviewed first-attempt causal calibration/first-usefulness failure**, not a population accuracy estimate or a legitimate Gemma-vs-other-model A/B.

**Code inspection:** `causal_answer_coverage_alignment.py` can prepend an Unverified statement without correcting all narrative claims. The pre-existing `causal_initiator_provenance_guard.py` depends on finite phrase recognition and bypasses Markdown table rows; the failed repair counter indicates the attempted synthesis correction was not fully successful. The exact internal drafts and issue labels are not present, so deeper failure-point attribution **NOT VERIFIED**. Do **not** add a case-specific passive-voice regex or repeat the incident. [Private-data-free source review](ANSWER-QUALITY-Q2-LIVE-CAUSAL-REVIEW-20261102.md) documents details.

**Measurement / next action:** For this one case, factual causal grounding **FAIL**, causal calibration **FAIL**, first-attempt usefulness for cause **FAIL**, read-only safety **PASS**, latency within preferred 45s **PASS**. Model-wide rates, precise claim denominator, same-packet paid/free comparison and Claude gap **NOT MEASURED**. Next registered independent read-only diagnostic: `device_mqtt_conflict` (“Why does Bedroom 3 Mesh show MQTT connected when its health is offline?”), preserve first answer + complete Technical JSON. Then compare source-witnessed causal and broker/endpoint separation against same frozen cross-domain packets before authoring a **general** claim-consistency design. Keep runtime add-on **0.18.371**, and native one-time Rule Machine creation independently blocked by upstream class proof.


## Q2 actual local-model first-answer trial — MERGED and measured (2026-11-02)

**Merged verified outcome:** [PR #1324](https://github.com/ienam-smarthome/HomeBrainOS/pull/1324) exact tested head `b18676cb153e856b0752b0a741c34478d71ac8d2`, main merge `16dd61c6037b37164e2dadd76cf1933f9efb3acf`; **8/8 CI green, 5,995 Python tests passed (two warnings)**. The Q2 actual local runner generated **8/8 nonempty first answers**, four byte-identical frozen prompt pairs using Qwen2.5 0.5B and Llama3.2 1B, without cloud model API calls or Hubitat/HA operations. Actual on-runner per-model **median wall: Qwen 2.337s; Llama 4.783s** across four cases, with model-load/runner conditions not controlled and no p95 evidence. The complete [source-bounded run summary](ANSWER-QUALITY-Q2-LOCAL-FIRST-ANSWER-RESULTS.md) keeps raw model answers out of the repository. **Semantic accuracy, first-usefulness, model-authored natural explanation, real Gemma/Claude comparison and production latency NOT MEASURED**: there were **0 human source-reviewed pairs**, and this is not an accepted Q4 performance ranking. HomeBrain runtime remains `0.18.371`.

**Next:** To truly measure Q2 model reasoning rather than just response transport, obtain privately held first responses on same frozen packet from configured Gemma Cloud and an alternative with explicit consent for any Cloud usage, review each against source, and pass authentic SHA-bound human review manifests through `scripts/answer_quality_paired_reviews.py`. No automatic paid API calls. Separate upstream Rule Machine class/dated trigger issue remains unresolved; avoid another HomeBrain-only identity or wording patch.

**Base and context:** The answer-hash-bound reviewer PR #1322 was merged as `a7b6c80712340fc81f278e9ad2530e2eddf12d9c`; its documentation-only PR #1323 was subsequently merged after 6/6 exact-head checks green. Real Gemma-vs-alternative first-answer quality remains **NOT MEASURED**. Upstream Rule Machine app-class verification remains an independent MCP server source gap, not a HomeBrain wording issue.

**Q2 question:** Can a genuinely executed, non-billable *local* same-prompt model run produce complete first answers with measured per-model wall times without touching Hubitat/HA or leaking model prose, and without falsely calling that answer-quality scoring?

**Candidate:** Add isolated GitHub-runner Q2 actual local Ollama first-answer trial for **four** fixed curated prompts across lighting, heating, MQTT and Rule Machine class identity, using tiny Qwen2.5 0.5B and Llama3.2 1B weights. Each receives byte-identical prompt once per case, frozen source digest and pinned temperature/seed/token settings; responses are hashed in memory and never logged/uploaded. The summary explicitly says **0 human-reviewed pairs**, **quality NOT MEASURED**, and **not Gemma/Claude comparison**. No live tool/gateway access, no production provider routing changes, no API token, no cloud model inference, no native rule authoring. GitHub hosted runner minutes/costs are separate and not independently priced.

**Metrics:** Before this candidate, real same-frozen-input natural answers generated by this tool **0**, after-result **8 actual first responses in 4 exact prompt pairs (verified GitHub Actions)**; unit tests are transport/guard tests only. If that run succeeds, report actual completed pairs and per-model wall times but **do not report semantic accuracy**. The 40 curated and 13 legacy source/rubric definitions are untouched. The main user-available Ollama Cloud Gemma model has **not** been invoked; a true Gemma comparison still needs separately authorised real model use and privacy review.

**Risk/rollback:** Offline additional CI job downloads small public weights; independent inference can fail or be slow, and a runner execution might use GitHub Actions plan minutes. No write to Hubitat/HA, no new production add-on version (still **0.18.371**). Rollback by reverting the local Q2 script, tests, isolated workflow and docs. [Protocol](ANSWER-QUALITY-Q2-PAIRED-REVIEW.md). Merge only all required exact-head checks green; a flaky model download must not be counted as a model failure on evidence.

## Q2 — exact first-answer reviewer binding MERGED (2026-11-02)

**Merged/verified:** [PR #1322](https://github.com/ienam-smarthome/HomeBrainOS/pull/1322), exact tested head `7a3894a02d735c52147d2c520ecf36eb59c82510`, merge SHA `a7b6c80712340fc81f278e9ad2530e2eddf12d9c`; **6/6 checks green**, **5,986 Python tests passed, two warnings**, release assurance smoke, offline scorecard integrity and repository validation passed. Delivered answer-bound Q2 human source-review CLI with strict two-arm packet/answer SHA joins and no raw-answer output. Installed HomeBrain add-on stays **0.18.371**; no hub writes, provider calls or changes to existing runtime. This is an **offline evaluation-integrity improvement**, not a measured factual accuracy, usefulness, latency, Claude-equivalence or Gemma-vs-alternative result. **0 genuine paired model answers independently reviewed** as of merge. No fabricated scores or automated truth grading.

**Next Q2 action:** Obtain **actual first-attempt answers to the same frozen evidence packets** from Gemma and an available alternative (provider/cost/latency and prompt-delivery context disclosed) and independently review them against source, then use the new SHA-bound comparison tool. The existing synthetic test grades are not a live/model baseline. No automatic cloud/billable inference; upstream native-rule identity source remains pending separately. If consented model evidence is unavailable, keep the Q2 baseline **NOT MEASURED**, and do not return to room-specific wording patches.

**Starting main:** `dab9b102560399e7e49b570203ea1d4b3cf7e9e6` after verified 0.18.371 Q1 live source-completeness regression and [PR #1321](https://github.com/ienam-smarthome/HomeBrainOS/pull/1321). The upstream Rule Machine identity-source repair is still external and unimplemented. Do not use more incident-specific source/answer patches or repeat that read-only inventory until the MCP source changes.

**Next cross-case gap found:** Q1 fixed-packet preflight `pair_metadata` verifies matching source packet digests for two **first attempts**, and the human scorecard can grade model/build/case; neither proves a human rubric was attached to the **exact answer** that generated each run's answer hash. Wrong-answer review attribution would produce an apparently precise but misleading model comparison.

**Q2 candidate:** `scripts/answer_quality_paired_reviews.py` composes the existing pair preflight and five-dimensional human scorecard with a strict per-arm answer-SHA linkage. It rejects changed/mismatched frozen packet hashes, nonfirst attempts, duplicate/unpaired/undisclosed mixed arm runs, incorrect answer hashes, unsafe reviewer identifiers and payloads containing prose/source logs. Aggregate output distinguishes eligible from actually reviewed pairs, shows true reviewer-supplied first-useful wins/losses/ties, original grounded-claim ratios and omissions. No model call is made; all review results are explicitly **human-supplied and not independently authenticated**. Model prompt delivery, private evidence review and provider billing remain external obligations. The frozen 40 curated and 13 legacy cases stay unchanged; no score is invented for an unreviewed packet.

**Hypothesis / expected metric effect:** Binding reviews to the exact first answer reduces attribution error and makes upcoming matched cross-model comparisons auditable. This is evaluation integrity, **not** evidence of improved production answers. Baseline actual paired source-reviewed sample **0**, post-change actual paired sample **0** (unless real answers/reviews later supplied): factual grounding, first-attempt usefulness, provider comparison, Claude gap and latency improvement **NOT MEASURED**. Next: run a consented small balanced comparison of the same frozen evidence packets through installed Gemma and available alternative, collect privately the raw first answers for independent source review, then compare only validated pairs. Do not trigger paid Cloud inference without explicit user billing consent.

**Safety/testing:** Unit tests use synthetic metadata/reviews to cover attribution failure and missing/contradictory first responses; complete exact-head CI was green before merge. Maintained runtime version remains **0.18.371**; no Hubitat/HA changes, permission changes, cloud spend or provider call. [Q2 protocol](ANSWER-QUALITY-Q2-PAIRED-REVIEW.md). Risk: new evaluator requires a separately retained private review bundle, and cannot itself authenticate a reviewer; rollback by reverting the Q2 CLI/test/docs only. Maintain the permanent Q0→Q4 charter.


## v0.18.371 installed read-only after-result — source completeness PASS, native class still absent (2026-11-02)

**Observed installed response:** New full read-only Technical JSON from **23:02 UTC** (one first response, `version=0.18.371` reported; deployed SHA not independently attested). Four successful upstream MCP reads including exact-ID thin app summary, plus one derived typed projection, **4.874s wall**, **957ms agent**, **938ms aggregate MCP HTTP**, `model=null`, no confirmations or changes. Compared with the earlier v0.18.370 sample (**3.237s wall**, **992ms agent**), latency differences are **not matched/reproducible** and cannot be assigned to the release.

**Expected regression verified:** `parentIdentityComplete=false` in the new raw projection, while `typesListComplete=true` reports only page-count completeness. `investigation_coverage.questionResolved=false`, `parents=[]`, one unverified Rule Machine candidate, and the exact proof gap `native-app-summary-class-namespace-unavailable` are internally consistent. The current exact-suffix match count remains **0** in the complete returned listings; historical one-time execution/cleanup remain unproven. This confirms the narrow evidence-truthfulness improvement in **one installed read-only case**, not overall grounding/first-attempt scores or an upstream parent resolution. [Privacy-minimal source review](ANSWER-QUALITY-Q1-NATIVE-IDENTITY-LIVE-REVIEW.md).

**Next dependency:** The upstream MCP server does not expose the required `hubitat/Rule Machine` class in either current read-only source. No additional HomeBrain-only patch or duplicate live question can prove it. Follow [upstream non-rendering type identity proposal](UPSTREAM-NATIVE-APP-IDENTITY-CONTRACT.md) when upstream write permission becomes available. Do **not** treat `hub_export_native_app` as read-only (it can instantiate/persist a cloner). Keep native one-time creation **disabled** pending source identity, dated trigger and writer safety. Continue Q2 frozen same-packet model comparisons independently of this external blocker. Overall real answer quality and Claude gap **NOT MEASURED**; no live Hubitat/HA writes.


## v0.18.371 — native source identity completeness corrected, merged (2026-11-02)

**Merged exact-head verification:** [PR #1319](https://github.com/ienam-smarthome/HomeBrainOS/pull/1319), tested head `536715dd4e0b1b95489dd8baed30bc1edc2fbaf0`, merge SHA `700fb033d23e79ad003e107b93a4633e1b63a8a5`, **7/7 CI checks green**, **5,972 Python tests passed, two warnings**, add-on smoke and scorecard integrity green. Released add-on **0.18.371**. New `parentIdentityComplete=false` when any native candidate remains unverified; `typesListComplete` keeps its returned-page meaning. Only derived Technical JSON completeness changes, not native class source, tool calls, final answer wording or permissions. **Installed after-result NOT MEASURED.** GitHub upstream permissions remain read-only; source proposal was documented but not submitted upstream. No Hubitat or Home Assistant writes.

**Real installed v0.18.370 first-shot:** The user repeated the read-only native Rule Machine inventory. **3.237s** wall, 4 source MCP reads + one typed projection, no model rounds and no mutations. Installed candidate parent **169** has class ID **18**, but the type catalog supplied no typed native Rule Machine class for that ID. The new `hub_get_app_config(summary=true)` call succeeded in **102 ms**, but returned no native `appType.namespace/name`. Exact current-rule suffix match count **0** in the reported complete app/rule pages; parent still **UNVERIFIED**, `investigation_coverage.questionResolved=false`, no rule created. A current name-match absence does not prove historical execution or one-time cleanup. v0.18.370's typed projection showed `parentIdentityComplete=true` despite an unresolved candidate: returned-page count completeness was conflated with native identity proof.

**Q1 hypothesis and change:** Complete lists can still contain an unprovable native type join. Set `parentIdentityComplete=false` if any Rule Machine parent candidate remains unverified, even when the returned type-page count is complete. Preserve `typesListComplete` as the returned-page count fact, the typed summary fallback and read-only permission boundary. Regression fixtures cover complete count with missing type join, source-typed positive/negative class evidence, conflict and no-candidate completeness. This is a generic claim-admission/completeness correction, not a device- or rule-name patch. Release `0.18.371` once all exact-head CI checks pass. Source-real live after, first-useful answer, paired answer quality, speed gain and model comparison **NOT MEASURED**. No live Hubitat or Home Assistant modifications.

**True upstream blocker:** Public MCP source `toolGetAppConfig(summary=true)` passes through `/installedapp/json/<id>` and omits the same source-typed platform class metadata its native writer already uses through `getAppByAppId(parentId).appType`. [Non-rendering upstream identity proposal](UPSTREAM-NATIVE-APP-IDENTITY-CONTRACT.md) captures a narrow source fix and strict negative tests, without granting writer authority. The GitHub connection has no upstream write permission; attempting to file an upstream issue returned 403, so upstream change **NOT SUBMITTED**. HomeBrain must not infer native class from app name, a bare built-in flag or rule counts. Native dated-one-time creation remains disabled pending parent, dated trigger semantics, safe 2-stage confirmation, backup and exact readback. No extra model calls. Continue Q1 source evidence and Q2 same-packet model comparison under the permanent charter.


## Q0 benchmark coverage expansion — 40 curated offline packets (MERGED, 2026-11-02)

**Merged result:** [PR #1317](https://github.com/ienam-smarthome/HomeBrainOS/pull/1317), exact tested head `28d218d80f4d594c88dbefc4ed52330f9cfb001e`, main merge SHA `9418e3ffe13fd207f8f7b1df15a69f00b4812c09`. **6/6 exact-head CI checks green**, including **5,970 Python tests passed, two warnings**, offline scorecard integrity, add-on container smoke, metadata and validation. The expanded fixture exports exactly **40 curated** packets and retains the **13 legacy** task definitions (53 total). The original 18 curated IDs/order remain frozen, no rubric fields leak into model prompts, and this documentation-only handoff does not change the add-on version **0.18.370**. No live Hubitat/HA operations. **Factual accuracy, first-usefulness, paired model quality and latency improvements: NOT MEASURED**, so no quality percentage is claimed.

**Milestone:** The charter's unfinished 40–50 curated benchmark-case target. Current main has 18 curated cases plus 13 distinct legacy tasks; this branch **appends 22 synthetic/anonymised cases** for 40 curated / 53 total without rewriting the original 18 prompts/evidence/rubrics, user histories, provider settings or add-on runtime. The old 13 task obligations remain separate. New cases cover exact historical windows, report/source time, command versus state, power/load, heat, fan, MQTT identity, typed native Rule Machine parent/one-shot semantics and read/write safety. No case is graded solely for being defined, and all new `review_status` values are `not_measured`.

**Hypothesis and expected metric effect:** A larger frozen cross-domain cohort will expose answer failures previously missed by the 18-case suite and support more honest same-packet before/after reviews. It is **NOT itself a measured improvement** in grounding, first-attempt usefulness, latency or Claude comparison. Baseline **0 source-reviewed frozen first attempts**, paired post-change answers **0**, model gap **NOT MEASURED**; no model inference, hub read or mutation performed.

**Tests and gate:** The offline packet exporter and scorecard tests are updated to expect 40 curated / 53 total, explicitly refuse grading on unreviewed cases, and check original 18 IDs/order unchanged. Run existing CI suite and merge only when all exact-head checks pass. Runtime add-on version stays **0.18.370**. Risk: expanded catalog changes the denominator for any full-cohort acceptance claim and adds reviewer workload; rollback is this benchmark-only branch or revert. No changes to native Rule Machine writing/permissions.

**Next real source acceptance:** The separately installed v0.18.370 **read-only** inventory question plus Technical JSON is still necessary to decide whether `hub_get_app_config(summary=true)` directly proves app 169's native namespace/class. Continue Q1 source evidence, Q2 matched offline model comparison and Q3 latency by *reviewed* cases; never count this fixture expansion as a production quality gain. Native one-time creation stays disabled.


## v0.18.370 merged — native app-type catalog missing built-in class 18 (2026-11-02)

**Merged and exact-head CI green:** [PR #1315](https://github.com/ienam-smarthome/HomeBrainOS/pull/1315), tested head `f4df327ad0e77751ce438fc778eb9266daf536ee`, merge commit `d5e2584e4f600c1e6028af5af33c0d5bce2c73ff`, **7/7 checks green, 5,969 Python tests passed, 2 warnings**. The fix performs a **single additional read-only** per-app summary to source-verify the exact native class only when the type-class catalog failed; it never infers parent 169 from names, app counts, a bare user=false flag or a contradictory catalog row. The app's missing systemAppTypes catalog is explicitly marked incomplete when upstream supplies that warning. **Actual installed v0.18.370 response, native parent classification and one-time creation: NOT MEASURED.** No Hubitat or Home Assistant writes, and native authoring remains disabled.



**Actual installed v0.18.369 evidence:** Rule Machine-named installed app **169**, `appTypeId=18`, no `hubitat/Rule Machine` built-in class in the app-type list, and zero exact one-time rule suffix matches in the complete reported current inventories. Three reads, no modifications, 2.786 seconds wall, 0 model rounds. Factual answer was on topic; parent still unresolved. Upstream `toolListHubApps` enriches community classes with best-effort built-in `systemAppTypes` from `/hub2/appsList`, so list/count completeness does not prove the built-in catalog is present. A second source, `hub_get_app_config(summary=true)`, reads the unrendered per-app identity `/installedapp/json/<id>` and may contain the native app-type pair; however upstream tests show it can also return only `{id,name,type,user}`. Do not presume native class identity or version.

**Candidate:** When the strict type-ID join fails, add one **read-only** thin summary for the first parent candidate. Admit parent only from matching app ID, built-in status, exact returned `appType.namespace=hubitat` and `appType.name=Rule Machine` with no conflicting type class. Otherwise describe the unavailable field. Label the type list incomplete when its own note says built-in classes were omitted. No extra provider round, no authoring or device mutation. Synthetic CI results and installed replay are pending. Historical one-time creation proven by PRs #445/#692/#697 but the newer writer still requires source-attested modern create/date contracts.


## v0.18.369 candidate — real inventory answer 2.667s but parent type link unverified (2026-11-02)

**Actual installed v0.18.368 first-shot source packet:** User repeated the same read-only Rule Machine parent and one-time suffix search. Exactly 3 successful nonmutating MCP source reads (app instances, app types, rule list), plus a typed host inventory projection; **0 model rounds, 2.667s elapsed** (MCP HTTP 832ms; agent 877ms). The v0.18.367 comparison had 9 Ollama Cloud model rounds and 44.626s wall time, albeit only one sample for each. This is clear one-case **latency** and on-topic answer improvement, not a population benchmark or fully resolved answer. Native Rule Machine-named instance **169** found, **exact native appTypeId/namespace join unverified**, no exact `(One-time YYYY-MM-DD HH:MM)` suffix matches in both complete returned lists, and no changes/confirmation. The UI correctly labelled the remaining parent question **Unresolved** but the Technical JSON incorrectly reported domain `existing_rule_verification` with unrelated action-tree/health requirements.

**Source gap confirmed in upstream tests:** The connected Hubitat MCP server's `ToolListInstalledAppsSpec.groovy` explicitly retains `appTypeId=null` when the Hubitat instance listing lacks the class ID. Thus the strict ID join in v0.18.368 can legitimately fail despite the parent app being named Rule Machine and built-in type rows being available. **Do not assert 169 as a verified native writer parent** without a direct typed relationship. v0.18.369 records `typeProofGap` (`instance-appTypeId-absent` vs `no-matching-native-app-type-id`) and bounded built-in Rule Machine app type IDs so the next read-only trace identifies the actual cause without exporting other apps.

**MERGED / CI ALL GREEN:** [PR #1313](https://github.com/ienam-smarthome/HomeBrainOS/pull/1313), tested head `eb0e663838bef68a6cce6a4a94b2bc37a815ba53`, merge commit `47a1298b507d0e87b6640c0475a3c147f5cfb889`. **7/7 checks passed; 5,955 Python tests passed, 2 warnings.** Earlier runs failed only on stale test expectations for the more explicit type-proof wording; corrected before all-green merge. The shipped add-on version is **0.18.369**. Live installed version replay, source `appTypeId` actual field and authoring restoration remain **NOT MEASURED**. User should update and repeat the identical read-only inventory question, retaining all Technical JSON.

**Q1 follow-up:** The common shared completion layer now distinguishes factual `native_rule_inventory` from a deep named-rule logic audit. It evaluates parent-identity type linkage, completed exact-suffix list and an optional source-matched native document (only when a surviving match exists and was requested), rather than requiring unrelated ordered actions/health/causal evidence. Partial parent evidence keeps the outcome **Unresolved**; complete source-joined inventory can report success without any model rounds. Tests use synthetic app types, missing IDs, bad namespace, truncated rule list and mutating/forged receipts. **Installed after v0.18.369 and real parent linkage: NOT MEASURED.** Native one-time authoring remains disabled pending actual parent and dated trigger evidence.


## v0.18.368 candidate — first-shot Rule Machine parent/one-time inventory was discarded (2026-11-02)

**Real v0.18.367 test:** A read-only question asked to identify a directly source-typed native Rule Machine parent app and list any rules with the literal "(One-time YYYY-MM-DD HH:MM)" suffix, using only read tools. It returned six successful nonmutating generic MCP receipts (instances twice, rules, name-filtered instances, app source ID 18, system app types), **no matched typed parent-ID or one-time-rule evidence**, and a generic partial **existing-rule action-tree** refusal with irrelevant comparison-controller language. 9 Ollama free rounds, 44.626s wall, 42.049s agent and 39.928s provider. Unsupported metric error from v0.18.366 was no longer present; the v0.18.367 safety fix worked, but first-shot correctness/usefulness did not.

**Root cause:** The existing-rule publication gate requires a fully verified ordered action tree, which is appropriate for auditing how one named installed rule behaves, **not** for a factual inventory of app instance type/parent and rule names. The gateway receipts only retained field-name summaries; model output was thrown away when no action tree read was made. This is an evidence task mismatch, not lack of inventorial reads.

**MERGED / ALL GREEN:** [PR #1311](https://github.com/ienam-smarthome/HomeBrainOS/pull/1311), tested head `6bf0abaf2e6e7e9af6145c91a68d096580cf2cef`, merged `3a5d891db78987f4cc900b604f4434d4c8d4f021`; **7/7 exact-head checks passed, 5,949 Python tests passed, 2 warnings**. Initial CI test-only failures were an assertion wording mismatch and missing accommodation for the correctly planned fourth **read-only** native document lookup. Both corrected and final checks green. **Installed live 0.18.368 replay: NOT MEASURED.**

**Delivered Q1 source-complete inventory route:** A narrowly scoped source-backed native parent/rule inventory path executes three allowlisted read-only source calls and projects the returned app-instance/type join and exact one-time name+ID matches. The app instance must link through an actual appTypeId to a type with namespace "hubitat" and name "Rule Machine"; unmatched parents remain candidates only. Complete-page/cursor checks guard zero-match claims. The first surviving one-time rule can receive one verified operation=read native document read (no write gateway delegated to the model). A factual inventory answer is not overwritten by the deep rule-action verification template. Tests cover type mismatches, incomplete pages, nonmatching names, no-model first response and no mutating tools. This stays generic to Rule Machine inventory, not a hardcoded household rule. **Production result, source IDs and paired latency: NOT MEASURED** until the same installed v0.18.368 question is replayed.


## v0.18.367 — fatal unsupported metric counter on read-only native-rule investigation (2026-11-02)

**Actual user-visible first-shot failure**: HomeBrain v0.18.366 returned `success=false`, `route=error`, `Request failed: Unsupported metric counter: investigation_source_checkpoint_offered` for a read-only request to identify the installed Rule Machine parent, list surviving `(One-time YYYY-MM-DD HH:MM)` rules and inspect an existing document. No complete Technical JSON with MCP receipts was returned. Do not infer that no reads executed or that Hubitat changed. This is an application exception, not a verified Hubitat failure.

**Code-derived cause**: `mcp_agent_orchestrator.offer_source_checkpoint` emits either `investigation_source_checkpoint_offered` or `investigation_source_checkpoint_suppressed` via an `if` expression. Neither was registered in `RequestMetrics.ALLOWED_COUNTERS`; strict metrics bookkeeping raises `ValueError` when the active request encounters that branch. `tests/test_request_metrics_registry_0_17_31.py` previously visited only direct `ast.Constant` call arguments and silently skipped `ast.IfExp`. Two injected `skill_investigation_followup.increment_metric` counters were also missing and could fail on a different live branch.

**MERGED / ALL GREEN:** [PR #1309](https://github.com/ienam-smarthome/HomeBrainOS/pull/1309), exact tested head `c7493c56dbafe0eaeb2b3808cec415f90d59e100`, merge commit `00d0e9645d1b90690ad8fa0a1244d793bb2df14e`; **6/6 exact-head CI checks passed, 5,935 Python tests passed, 2 warnings**. The released add-on is `0.18.367`. No live Hubitat or HA changes were made; this verifies the local metrics exception cannot recur through the covered branches, **not** the correctness of a native rule-parent investigation.

**Patch**: Register four bounded names and extend the AST regression scanner to include both conditional string leaves and injected metric callback callsites. A synthetic `SourceCheckpointBudget` replay covers both permitted and suppressed offers with active `RequestMetrics`, preserving three-offer budget and no write/tool changes. Bump maintained add-on version to **0.18.367**. **Installed after-result, completeness, first-pass quality and latency are NOT MEASURED** until a replay of the exact read-only user prompt. Do not claim the native parent or one-time rule existence until typed Hubitat tool output supports it.


## One-time native Rule Machine restoration — historical PR reconciliation and offline candidate (2026-11-02)

**User correction accepted:** Earlier HomeBrainOS genuinely created dated one-off rules. PRs #445, #692, #697 supplied the relative scheduling, Hubitat-local ISO clock and DST correction. PR #698 installed guarded cleanup of expired one-off rules, and #951 documented a live Rule Machine child with actions despite a timeout. The user's latest UI shows the one-time cleanup scheduler enabled, with 41 rules checked, zero currently eligible, no deletes or failures at 07:00 on Nov 2. That proves the **cleanup** is still scheduled, not that modern **creation** works. The current native MCP server replaced the legacy shortcut; v0.18.361's confirmed create failed with `Unknown hub_set_rule property` (PR #1296).

**MERGED / ALL GREEN:** [PR #1307](https://github.com/ienam-smarthome/HomeBrainOS/pull/1307), exact tested head `fb6ccb2a4449eeebbf3469e018f8270667b7279c`, merge commit `0a3f9c708a8914d79d79918f8340eb401e84f1ca`; **6/6 exact-head CI checks passed, 5,930 Python tests passed, 2 warnings**. Initial failure was a test assertion accessing the action fields at the wrong JSON level, fixed before final run. Production version unchanged at **0.18.366**; no Hubitat/HA read or write occurred in GitHub workflow. These are structural/safety tests, **not** proof of restored live native writes.

**Delivered offline restoration foundation:** Added pure `scripts/native_one_time_rule_compiler.py`, which translates a fully source-attested **native dated** one-off Switch template, verified native RM parent app, installed native write schema, target Switch ID and future Hubitat-local time into an unconfirmed atomic native create candidate. Unlike a static shortcut rename, it refuses a daily 22:00 exemplar, unknown date fields, mismatched native label/timestamp, stale timing, absent parent, malformed typed settings, and unsupported commands. Explicit `write_ready=False`; no runtime model, confirmation, Hubitat creation or disabling is enabled. The dated sample in regression tests is **synthetic**, not proof of installed native behavior. The current home example is daily and does not meet the production gate.

**Next:** From an actual read-only installed MCP source retrieve the correct native Rule Machine parent identity and, if available, an existing **dated** native Rule Machine switch-action document; alternatively prove the same semantics in independently isolated upstream native tests. Only then connect the adapter to deterministic authoring, existing 2-stage unique-name preflight, fresh user consent, recovery/backup, timeout reconciliation and exact typed post-write readback. In no circumstances resend the expired 15:35 one-time action. **First-pass benefit, correctness, real creation against current MCP, latency and model gap: NOT MEASURED.** See [native compiler readiness](NATIVE-RULE-MACHINE-COMPILER-READINESS.md).


## v0.18.366 candidate — Q1 source-complete existing-rule read (2026-11-02)

**New complete live packet:** Installed `0.18.365` correctly classified the user-requested native rule inspection as `live-read`, required **no confirmation**, and made **zero mutating tool calls**. However, it returned a **partial/unresolved** finding after **43.586s wall time / 42.095s agent / 39.829s provider, five model rounds, five read tools**. The successful receipts were app inventory, rule-health, local variables and two generic app-configuration reads; none was the expected native `hub_set_rule(operation=read)` document. `read_only_model_write_blocked=1` records that the model tried an unauthorised mutating gateway once; that was safely blocked. The final report mentioned unrelated potential controller interference and duplicate rules rather than the requested narrow native document. This **is a failed first-attempt useful response** for this specific frozen prompt, not an overall model benchmark score.

**Root-cause evidence:** The installed native rule document was successfully read during a previous controlled, approved `hub_set_rule` call. `ToolDiscoveryCatalog.activate_investigation_read_view` intentionally removes mixed read/write `hub_manage_*` gateways; a model cannot safely regain them in read-only reflection mode. `mcp_agent_orchestrator` source prefetch for named installed rules had only health/variables and generic app settings, so the stronger native read was never attempted, even though its narrow effect classification was repaired in 0.18.365.

**Q1 candidate repair:** For a named existing rule, make **one host-owned, contract-validated native document read** when the installed gateway is available. It is never exposed as a model-authorised general management gateway. Require matching rule ID, typed settings, ordered action rows, trigger and condition structure, no truncation/sensitive fields. Give a bounded typed source packet to natural model synthesis, mark `stored_logic` verified only when complete, and skip redundant weaker prefetches; otherwise fall back to prior partial reads. No writes, confirmations, native form open, or Hubitat/HA changes.

**Actual after outcome, p50/p95 and Claude-like quality: NOT MEASURED.** New mock source tests/CI must pass before merge. Native creation still blocked on verified direct Rule Machine parent link and dated one-shot trigger semantics. Next live Q&A must reuse the original same question, model and source scope, reporting full answer and Technical JSON.


## v0.18.365 merged — native document read falsely treated as sensitive write (2026-11-02)

**New real source packet, installed v0.18.364:** An explicit read-only request for an existing native Rule-5.1 rule returned a pending confirmation to run `hub_manage_native_rules_and_apps`; **first response 24.032s, 3 model rounds, 2 read-only MCP calls**. After approval, a structured `hub_set_rule(operation="read",rule_id=<verified native rule ID>,confirm=true)` call returned successfully in **373ms MCP / 3.793s wall, one model round**, with typed settings: `tCapab1=Certain Time (and optional date)`, `time1=A specific time`, `atTime1=22:00`, `actType.1=switchActs`, `onOff.1=false`, `onOffSwitch.1` as an array of switch-device IDs, and an action `method=getOnOffSwitch`. This **is a genuine current-request native read receipt**, unlike the prior unsupported model claim. It is an existing *daily* rule; no parent link or one-time dated trigger semantics are proved. Stored `onOff.1=false` is a configuration value, not evidence the device physically switched off.

**Source defect:** The native management gateway's `hub_set_rule` selector starts with `set_`; `_operation_effect` classified it as `SENSITIVE_WRITE` despite embedded `operation=read`. That incorrectly queued confirmation, recorded `mutates=true`, and published `request_class=write`. The upstream native `toolSetRule` explicitly dispatches `operation=read` to `toolGetRuleDocument` independently of boolean `confirm`; other native `create/update/form` operations can modify hub state, including partial changes.

**MERGED / ALL GREEN:** [PR #1304](https://github.com/ienam-smarthome/HomeBrainOS/pull/1304), exact tested head `b2644cd3800316c0b05a9ceb5017578841ae2c40`, merge commit `e09cfdcaa75c8b90effd2bfde9f0cfeba664f7a7`; **7/7 exact-head CI checks passed, 5,884 Python tests passed, 2 warnings**. Initial suite failure came from insufficient scripted FakeAI finalisation responses, not the operation classifier; corrected before merging. **Real installed follow-up v0.18.365: NOT MEASURED.**

**Delivered change:** Whitelist only the exact, validated nested native document read envelope on native management gateway(s), require positive numeric rule ID, prohibit unknown/extra fields and mutating operations, permit only documented read sections/paging. Tests must prove no confirmation, `effect=read`, `mutates=false`, `request_class=live-read`, and continued denial of all writes on explicitly read-only questions. No change to native create compiler; no live Hubitat/HA mutation. **One complete pre/post same-question result is not yet available, therefore first-shot usefulness, accuracy and latency A/B are NOT MEASURED.** The two observed phases (24.032s then 3.793s) are not comparable independent runs; do not claim latency acceleration from them.


## v0.18.364 merged — coordinated no-write instructions, source provenance (2026-11-02)

**Real live regression on v0.18.363:** A requested read-only inspection of an existing native Rule Machine time-trigger/Switch OFF rule returned **Unresolved / request_class=write**, replacing the investigation with "I could not verify that this action actually ran on Hubitat", despite **5 read-only MCP receipts, 0 writes, no confirmations**. **7 model rounds, 35.612s total (31.854s provider), 5 tools.** This was **not a requested action**. The model's separate purported rule-4136 results named parent 169, fields `tCapab1/time1/atTime1`, `actType.1/actSubType.1/onOffSwitch.1/onOff.1`, but the complete Technical JSON **does not include the claimed `hub_set_rule(operation="read")` call**. Parent 169 was inferred from equal inventory counts, not proven direct parent ID. Treat sample as tentative; no one-time calendar-date semantics verified.

**Confirmed source flaw:** `explicitly_read_only_request()` reads the comma-separated prohibition "`Do not open native forms, create rules, submit confirmations or modify anything`" as if the `, create rules` segment were a standalone affirmative instruction. It revokes the user's read-only request; `_explicit_mutation_request` then sets the write flag, and `_unverified_mutation_guard` overwrites the natural read-only answer because no write receipt exists. Corrective v0.18.364 candidate maintains negation over one coordinated list, but still recognises *independent* positive imperative clauses after sentence/contrast boundaries. Negated `open/submit` are also stripped from other non-read-only analysis prompts.

**MERGED / CI ALL GREEN:** [PR #1302](https://github.com/ienam-smarthome/HomeBrainOS/pull/1302), exact tested head `fb059b0790bfa514d7cc471258d946231212e8f0`, merge `021c5bc2ba9d37c6ac87d46549e97cc29f1b5467`. **8/8 exact-head checks passed**, full **5,854 Python tests, 2 warnings**. Initial CI run found 2 test failures, corrected by distinguishing comma-list negation from new-sentence positive commands; rerun fully green. **Installed live v0.18.364 not yet verified.**\n\n**Expected improvements / limitations:** Zero false write classification and preserved answer for synthetic read-only source cases; no new model or MCP rounds from the code change. **Measured synthetic regressions passed; real first-pass usefulness, 35.6s → after, matched latency, source-grounded native field score and Claude comparison: NOT MEASURED.** No live Hubitat/HA modifications. Native creation still blocked on authenticated installed-native read/parent, one-time date semantics, confirmation and readback. See [native compiler readiness](NATIVE-RULE-MACHINE-COMPILER-READINESS.md). Continue benchmark-first roadmap.


## v0.18.363 merged — delayed schedule refusal must not show green Success (2026-11-02)

**Real reported regression:** On live v0.18.362, `block TV after 15mins` returned `request_class=live-read`, `metrics.outcome=success` / green Success, no confirmation, no rule ID, no device or rule write. It made **one read-only `hub_get_tool_guide` call (180ms)** and detected `native-document`; the user action **did not happen**, so the success label was materially wrong. **No current native rule create implementation** is verified. Exact user-visible UI payload and timestamp received. Do not imply the command succeeded simply because the guide was read.

**MERGED / CI ALL GREEN:** [PR #1300](https://github.com/ienam-smarthome/HomeBrainOS/pull/1300), tested head `9d8bdd0d0572af1772cbf8fe02397d703406d1ea`, merge `219f1abbc679cbcd092b12e640c31bf1a51936e7`; **7/7 exact-head checks successful**, full **5,842 Python tests, 2 warnings**. **Focused correction in v0.18.363:** A bounded recognised scheduling imperative remains **`request_class=write`** even when the immediate-control guard correctly refuses to execute delayed commands directly. Explicit read-only/review requests still have no write authority. Installed native or unknown/failed contract checks now increment privacy-safe `rule_writer_native_unsupported` / `rule_writer_contract_unverified` counters, yielding **`unresolved`**, not success. The refusal is shorter, names the actual incompatibility and affirms no write was queued. New source-mocked tests reproduce the exact original wording, assert no confirmation, no write and no unnecessary AI rounds; the existing legacy contract remains guarded. No Hubitat/HA calls or live mutations were performed by development. **v0.18.363 is merged but NOT verified installed/live; first-useful answer, latency A/B and actual rule creation remain NOT MEASURED.**

**Important limit:** This corrects intent/outcome and communication only; it does **not** turn an unsupported native `hub_set_rule` schema into working creation. A functional native compiler still requires proven installed parent ID, native typed trigger/action fields, expiry/timezone/one-time semantics, fresh consent, verified atomic child lifecycle and readback. Upstream warns that even opening native forms can mutate state. Continue the documented native-source verification before enabling any native writes.


## Native Rule Machine authoring — next unfinished milestone, offline preflight (2026-11-02)

**MERGED / ALL GREEN:** [PR #1298](https://github.com/ienam-smarthome/HomeBrainOS/pull/1298), tested exact head `50c9babcc7837b8bf0bf85fdd509a508cb449bb8`, merge `1d6775ec7ebf75c92c2fd3411031b331cb2a4f89`; **6/6 checks green**, **5,830 Python tests passed, 2 warnings**. Offline-only change under `scripts/` and synthetic tests; **no add-on version bump** and no production behavior change. Native-document migration is still gated on source-attested native capability fields and a verified parent. Added `scripts/native_rule_document_preflight.py` for *pure structural* checks of the installed native guide, unconfirmed create schema, native Rule Machine parent and one atomic trigger/action typed-field batch. A positive shape result **never** enables writes (`write_ready=False`); no model/gateway confirmation route was altered. See [native compiler readiness](NATIVE-RULE-MACHINE-COMPILER-READINESS.md). The source-derived requirement to inspect native forms is not automatically a safe read: upstream explicitly says a form `open` may mutate state. No live Hubitat/HA calls were made. Synthetic tests include malformed nested metadata, wrong parent, duplicate/selector fields and batch-integrity negatives.

**Answer quality:** Same-packet accuracy, first-pass usefulness, p50/p95 performance and model A/B are still **NOT MEASURED**; there are no new live results and no accepted improvement percentage. Keep the 14.624s Hallway TRV first-shot timing as an observation, not a paired optimization. Next: before a real writer, obtain installed-server *nonmutating* authoritative native field/one-time semantics, implement confirmation and readback, and test blocked partial creation. Do not retry the expired 15:35 rule or infer absent rules without fresh read-only inventory.


**Charter:** [ANSWER-QUALITY-CHARTER.md](ANSWER-QUALITY-CHARTER.md)  
**Last baseline assessment:** 2026-11-02; **1 user-rated useful first-attempt live answer (grounding not fully authenticated)**, **2 complete source-bounded cross-domain diagnostics** (recorded command versus bridge reporter; device health versus MQTT status). The official scorecard remains **NOT MEASURED**.  
**Most recent verified installed live add-on:** `0.18.361`. Hallway TRV read-only first shot **Success**, 14.624s, four provider rounds/four tools; per-round timing receipts verified live (3,817ms + 2,036ms + 1,852ms + 3,416ms). Current temperature 21.5°C, battery 96%, temperature events split correctly inside/outside requested 15 minutes; setpoint source not independently inspectable; sleep/reporting inference unverified. In same installed version, **one-time Rule Machine write FAILED** with exact `Unknown hub_set_rule property` (modern upstream native-document contract vs HomeBrain legacy shortcuts) despite confirmed approval. **v0.18.362 fail-safe contract guard merged 6/6 green, but native rule creation remains UNSUPPORTED until a separate verified writer is implemented; not live installed yet.** Earlier v0.18.360 Bedroom 1 Light nonempty 20-min accepted 25.338s, zero-event branch not live verified. No matched A/B/Claude-parity scores.
**Live Hubitat/HA mutation:** none authorised by this quality programme.

## v0.18.362 merged — native Rule Machine writer API break; confirmed write stopped (2026-11-02)

**REAL FAILED USER-CONFIRMED WRITE — primary issue:** On installed v0.18.361, user asked for a one-time Internet blocking Rule Machine schedule on **Block Media-Google-TV-Streamer**, selected device **6923**, intended **2026-11-02 15:35 local**, preflight started ~15:20 UTC, used read-only hub timezone, Internet-room target resolution, and 41-rule duplicate list. HomeBrain queued a confirmation with `confirmation_required=true`. After user confirmed, it called `hub_manage_rule_machine(tool=hub_set_rule, args={name, addTrigger: Certain Time at 2026-11-02T15:35:01, addAction: runCommand(off,deviceIds:[6923]), confirm:true})`. The gateway **rejected the write with the exact error `Unknown hub_set_rule property`**, returned no `appId`, and HomeBrain reported not fully completed. No creation was verified. The error itself is strong evidence the submitted shape was rejected, but without a fresh native rule listing no claim is made that all partial side effects are impossible. Do not retry stale 15:35 one-time schedule, invent a new event time or reuse the old confirmation.

**Verified upstream code cause, not a device/confirmation failure:** Current [kingpanther13/Hubitat-local-MCP-server](https://github.com/kingpanther13/Hubitat-local-MCP-server) `libraries/mcp-native-documents-lib.groovy` `toolSetRule` checks top-level keys against `operation,rule_id,args,confirm,bestPracticeKey` and emits the **identical** error for retired top-level `name,addTrigger,addAction`. It now expects native document `hub_set_rule(operation='create',args:{parent_id,name,changes:[{part,value},...]},confirm:true)`, with exact **Rule Machine parent id** and native typed trigger/action fields. The upstream source supports a contract/version-family mismatch; the actual installed MCP server's version and complete `set_rule_reference` guide were not independently fetched in this development turn. Do **not** fake the native `changes` payload by renaming shortcut fields.

**MERGED / CI ALL GREEN:** [PR #1296](https://github.com/ienam-smarthome/HomeBrainOS/pull/1296), tested exact head `1f0095e57b37a92f7467fb66df6d51acf77705a7`, merge SHA `3f0a14e12cff599c3e53f91c247c9b8f042a45fc`. **6/6 checks green**, full **5,803 Python tests, 2 warnings**, container, metadata and validation gates. Two initial CI rounds exposed synthetic legacy fixtures missing newly required guide evidence; those tests were corrected to advertise the legacy authoring contract explicitly, not by weakening production checks. New source-mocked tests cover modern native writer refusal, legacy shortcut acceptance, guide-unavailable fail closed, confirmed create-group revalidation, and read-only/no-write promises.

**Implementation and safety boundary:** `rule_writer_contract.py` classifies only the read-only installed guide `hub_get_tool_guide(section='set_rule_reference')` as `legacy-shortcut`, `native-document` or `unknown`. `RuleAuthoringService.propose` checks compatibility **before** normal deterministic schedule authoring can queue a confirmation; confirmed create replay preflight checks it again to guard against upgrades between proposal and approval. Modern native/unknown schema returns a clear no-write explanation and does not call `hub_set_rule`. Existing legacy supported, identity/switch command/duplicate checks intact. The guide text is not retained as private raw logs; only contract-class summary. No live Hubitat/HA calls, mutations, schedule edits, app creation or device controls were performed by development. **v0.18.362 has NOT been installed/verified live.**

**CRITICAL LIMIT — RULE WRITING IS NOT FIXED:** The release prevents an incompatible write; it **does not create or modify native-document Rule Machine rules on newer upstream**. Next substantive milestone is a genuine source-negotiated native authoring compiler, not another shortcut patch. Before enabling it: read installed `set_rule_reference` and schema, discover authoritative parent ID and native typed trigger/action `fields`, validate time semantics (including one-time expiry and current hub timezone), ensure backup/duplicate and idempotency protections, stage/confirm user action and verify native rule/document/trigger/action/readback with no partial active shell. Do not silently substitute Visual Rules or create an empty rule then patch after. Never perform a live write without fresh explicit approval.

**Parallel Answer Quality evidence:** The user also supplied the first **v0.18.361 Hallway TRV** live status/history response and Technical JSON: `Success`, **14.624s**, Ollama Cloud `gemma4:31b`, four provider rounds / four tools, source-backed current temperature **21.5°C** and battery **96%**, 15:04:08.438 source temperature report **inside** the last-15-min window and 14:34:09.236 prior report **outside**. Heating setpoint 21.0°C in prose but not independently exposed as a typed receipt in the retained JSON; do not count as source-verified. The response's inference of sleep/reporting cycle from a two-event 30-minute gap is **unverified hypothesis**, not established mechanism. New `model_round_details` latency instrumentation **VERIFIED live**: 3,817ms answer(no tools), 2,036ms tool calls(17 declared), 1,852ms tool calls(17 declared), 3,416ms answer(17 declared); ~11.1s provider in 14.624s total. `requested_event_window_packet` and `current_state_clock_packet` were absent in that trace, although a separate source event history existed; investigate source-path selection before declaring those requirements satisfied. This is one first-shot performance observation, not a matched speed A/B or Claude-quality score.

**Next work priority:** Native Rule Machine compatibility is a functional blocker with a concrete independently checked upstream cause. Continue source-derived native authoring design/verification under explicit write permission gate; concurrently keep the core answer-quality charter: first-useful answer, source attribution, truthful uncertainty and efficient rounds. Avoid claiming Rule Machine write works simply because this fail-safe CI is green. The previous one-time 15:35 rule must be read-only checked for existence before considering a newly scheduled rule, and any new schedule needs explicit fresh authorization.

## v0.18.361 verified merge — per-round provider diagnostics before latency optimisation (2026-11-02)

**MERGED on exact tested SHA with ALL GREEN:** [PR #1294](https://github.com/ienam-smarthome/HomeBrainOS/pull/1294), tested head `b553605aad834a18e5e5894cb3dcbbcaf6afc4e9`, merge SHA `c42ae97ccaceb64fab9c9bdda1fadfcdca6473c5`. **7/7 CI checks succeeded**, full Python suite **5,797 passed, 2 warnings**, add-on container smoke, repository metadata and validations. This release changes only diagnostics, **not** tool permissions, final narration, model calls or read/write behavior. No live Hubitat / Home Assistant changes. v0.18.361 has NOT been installed or tested live as of this handoff.

**Why:** The user's real v0.18.360 Bedroom 1 Light historical-first-answer was source-correct (8 in-window switch reports, two older excluded; `requested_event_window_packet=1`), but took **25,338 ms**, of which **20,078 ms provider** over **five gemma4:31b Ollama Cloud model rounds / five tools**. The old `model_round_details` had only `{model,provider}` entries per round, not enough to tell whether cost was tool selection, final synthesis, unnecessary read iterations or provider variability. This is ONE source-specific case, not proof the window packet or planner made it slow.

**Diagnostic implementation:** `RequestMetrics.record_provider_model` retains optional `elapsed_ms`, `tool_call_count`, `result_kind=tool_calls|answer`, `declared_tool_count` in each of the existing bounded per-successful-round `model_round_details` rows. Ollama streaming and nonstreaming, one permitted empty-message recovery, and Claude success paths report using monotonic wall clocks. Timings include round preparation/transport and possible empty-message recovery, **not isolated server inference time**; raw failed attempts do not count as successful rounds. The existing provider aggregate remains unchanged. No prompts, tool names/args, content, device identifiers, secrets or raw logs are saved in new fields. Synthetic transport tests verify response-type classification, round durations, zero tool final answer, privacy, numeric bounds, cap of 64 rows, failed request and per-request isolation. **Actual live timing savings NOT MEASURED** and no speed reduction is claimed.

**Next Q3 milestone:** After installing v0.18.361, capture **ONE fresh independent, read-only initial answer** with full Technical JSON; inspect `model_round_details[].elapsed_ms`, `result_kind`, `tool_call_count`, `declared_tool_count`, total provider and elapsed time, and original user usefulness. Decide whether round overhead or inference delay is the measured bottleneck BEFORE making a planner optimisation. For true latency comparison use same question and same frozen source receipts; distinct live questions are NOT an A/B. Prefer test on a nonrepeated domain. The special v0.18.360 successful **explicit-zero** source receipt without `observedEvents` is still **NOT VERIFIED LIVE**; whenever a genuinely independent empty-history source arises, check `requested_event_window_packet=1`, but don't fabricate a zero-event device or repeat known fixed cases to claim acceptance.

## Live v0.18.360 Bedroom 1 Light — positive nonempty rolling-window acceptance, latency concern (2026-11-02)

**SOURCE-REVIEWED FIRST ANSWER:** User supplied original screenshot and full Technical JSON for an explicitly read-only Bedroom 1 Light query: current state, ON/OFF events within the **last 20 minutes**, separate older reports from actual window activity, and distinguish reporter, command and listener. Installed add-on `0.18.360`, model `gemma4:31b` on Ollama Cloud free routing, outcome `Success`, **elapsed_ms=25338**, provider **20078 ms**, agent **22460 ms**, **5 model rounds / 5 tools**, one discovery, zero writes. This is **one real 25.338-second historical investigation**, over the 15s common-status goal but within the preferably-under-45s complex-investigation goal; NOT a median/p95 or matched A/B.

**Verified target/state/window:** Exact `homebrain_resolve_device` chose Bedroom 1 Light **ID 7840**, `reportedAttributes.switch=off`, `level=50`. The history receipt at **2026-11-02 14:13:51.501116 UTC** supports approximate rolling window **13:53:51.501–14:13:51.501 UTC**. The final natural answer presented **13:53:51–14:13:51**, eight switch state reports inside (**four on/four off**), correctly listed:
- 13:55:57.330 on → 14:02:41.885 off
- 14:04:28.441 on → 14:05:16.501 off
- 14:07:15.578 on → 14:08:07.559 off
- 14:10:51.471 on → 14:11:01.524 off.

**Older records and bounds:** The same successful typed `homebrain_device_history` (`attribute=switch`, `hoursBack=1`, `sourceEventCount=10`, `analysisEventCount=10`, `observedEventsTruncated=false`) contained two **prior** state reports: 13:25:12.168 on and 13:32:00.365 off. The model properly identified them as *context outside* the requested window. Critically, the one-hour temporal analysis also supplied `intervalCount=5` and **`totalActiveSeconds=923` (15m)**; the final answer did **not** misreport that wider-scope total as on-time inside the 20-minute request, unlike the prior FP300 failure. Source history itself still says `historySourceIntegrityVerified=false`; it is not independent physical execution/exhaustive source coverage.

**Provenance:** All ten observed state rows had `type=physical` and `producedBy=Matter Hue Bridge Pro`; that establishes Hubitat's reported event classification/bridge producer, not who instructed the bridge or whether a person acted. `triggered[]` listed listeners including Maker API, SenseCap Settings, Bedroom 1 Light Off and Google Home; those are **not proven command issuers**. The response correctly limited “no commands” to **that retrieved event stream**, not all Hubitat app logs. The supplied later Claude comparison gave separate earlier history, a 12:51 brightness command outside the time window and precise milliseconds; Claude's raw tool transcripts were not supplied, so this is qualitative and not a same-source A/B. The user did not explicitly rate this first answer; human usefulness remains unscored rather than declaring a new user-rated pass.

**Actual runtime acceptance flags:** `requested_event_window_packet=1` **and** `current_state_clock_packet=1` are in Technical JSON counters, confirming the source timing guidance ran in the installed add-on. **However this tests only the NONEMPTY history path**, since `observedEvents` contained ten rows. It does **NOT independently validate** the new v0.18.360 missing-array + explicit-zero-count admission path that motivated that release; the earlier v0.18.359 zero-event test had no packet. Do not claim the zero-event case is fixed in production without a true live sample.

**NEXT evaluation milestone:** Prioritise **cross-domain, source-matched first-answer and latency measurement**, not another room-specific answer patch. For performance, compare round traces and prompt/token size on the same replay sources before asserting that five model rounds or the clock/window packets cause extra provider latency; the 20.078s provider component dominates this one run but attribution across rounds is NOT available. When a genuinely new/independent read-only prompt yields a complete **explicit-zero** typed history receipt, check that `requested_event_window_packet=1` on that actual *empty* source case and that 0 rows is not claimed to prove no physical events or commands. Preserve natural concise answer/provenance rules, add no unmeasured model/tool calls, and leave live Hubitat/HA untouched.

## v0.18.360 merged — v0.18.359 zero-event status first shot and packet admission (2026-11-02)

**MERGED with exact-head ALL GREEN:** [PR #1291](https://github.com/ienam-smarthome/HomeBrainOS/pull/1291), tested head `8fa38a911163a0e5bc4c3c49fb5cea91a078bd2a`, merge commit `29663b1896210c7665ab6565aff52119fd38ed6a`. **7/7 checks passed**, **5,792 Python tests, 2 warnings**, container smoke, metadata and workflow validations. No Hubitat/HA reads, configuration or physical commands were made in the development process. v0.18.360 is **merged, NOT yet installed/live-measured**.

**Real first-shot v0.18.359 — Livingroom Light 1 (device 7805), source result substantially correct but source packet NOT activated:** User supplied screenshot, full Technical JSON and a separate later Claude explanation. Read-only prompt asked for ON/OFF count **over the last 20 minutes** with causal-origin caution. Model's response was **Success**, `switch=off` (supported by two exact selected-device receipts), **0 returned switch events**, “12:33 to 12:53 UTC” (minute-rounded) with saved reads at **12:53:50–12:53:56 UTC**. The direct filtered `hub_list_device_events` `attribute=switch,hoursBack=1` returned zero; an unfiltered fallback also returned zero. The local `homebrain_device_history` receipt had `attribute=switch`, `sourceEventCount=0`, `analysisEventCount=0`, `historySourceIntegrityVerified=false`, and **no `observedEvents` key**. The conclusion “zero switch state reports returned inside this window” is justified by these bounded read-only sources. It is **not** proof that physical activity, unrecorded writes or automation commands elsewhere were absent. The answer's final sentence could distinguish those concepts more carefully. Claude's later 20-minute query ended about six minutes earlier, and Claude read additional 24h source history; the answers are not a matched temporal/source A/B.

**Runtime and flag:** `elapsed_ms=16228`, Ollama Cloud `gemma4:31b` free, **5 model rounds / 6 tool calls, 1 discovery, zero writes**, UI `Success`; provider ~11.925s; agent 14.326s. This is one **16.228s** observation above the 15s status target; no median/p95 distribution. `current_state_clock_packet=1`, but **`requested_event_window_packet` was ABSENT**. Therefore the v0.18.359 correction was **not** exercised in this empty-event acceptance; merely producing a correct zero count does not establish the new planner worked.

**Cause / v0.18.360 fix:** `requested_event_window_evidence.render_requested_event_window_evidence` filtered out any history receipt whose `details.observedEvents` was missing or not a list. The device history service intentionally omits that field for a zero-event result, while providing exact integer zero `sourceEventCount` and `analysisEventCount`. This new source helper now admits an **absent event array only when both source and analysis counts are explicit integer zero on a successful typed read-only history receipt**; absent/malformed/nonzero counts and contradictory empty projections do not become zero. It emits the same bounded-window integrity caveat, does not invent physical inactivity, and keeps model-written final prose, exact device/source scope, safety guards and one existing final model call unchanged. Anonymous offline tests reproduce the actual receipt shape, verify 20-minute boundaries, generic zero-motion history, invalid counts, failed/write receipts, cross-target mismatch and source-packet registration. **Live v0.18.360 token/runtime effect or model compliance NOT MEASURED.**

**NEXT acceptance / Q3 direction:** After installing v0.18.360, run **one fresh, unrelated read-only history question with an explicit relative time window**, ideally where few/zero events are expected; send initial answer + complete Technical JSON. Check for `requested_event_window_packet=1` if an exact typed `homebrain_device_history` receipt is returned, whether it distinguishes zero source reports from no physical activity or commands, and exact start/end accuracy. Avoid rerunning Livingroom Light 1, Hallway FP300, Freezer/Fridge and Washing Machine as repetitive fixed-case benchmarks. Record latency, rounds and provenance separately. Continue cross-domain quality measurement rather than a new case-specific patch.

## v0.18.359 merged — first cross-domain motion-history evaluation: requested-window failure (2026-11-02)

**MERGED exact-head ALL GREEN:** [PR #1289](https://github.com/ienam-smarthome/HomeBrainOS/pull/1289), tested head `6d738855d023ae4fbbe741574552abb9c0d1fdb8`, merge commit `726b252de7c9eca0ffff23d4e6b8ae668de05bfa`. **7/7 CI checks succeeded**, full Python suite **5,784 passed and two warnings**, metadata, container smoke and validation gates. **No live Hubitat / HA changes**; v0.18.359 **NOT yet live-verified/installed**.

**Actual first-run v0.18.358 Hallway FP300 test — NEGATIVE quality benchmark:** User supplied complete screenshot and Technical JSON plus a later Claude answer for the same nominal question asking for **last 30 minutes** of reported motion/presence and a distinction between events and automation commands. Installed add-on `0.18.358`, online Ollama Cloud `gemma4:31b`, free tier, **17,468 ms elapsed, 5 model rounds, 7 tools, 1 discovery, one ambiguous broad device-resolution step**, no writes. UI `Unresolved`; completion had model-proposed competing hypotheses whose physical/upstream origin was not independently verified. The native output wrongly called **four active/inactive pairs totalling 252 seconds** activity **in the last 30 minutes**. Yet its own `homebrain_device_history` returned a broader **1-hour** history for the child `Hallway FP300 sensor` (ID 7752). All eight events and four paired intervals lay **11:18:32–11:33:47 UTC**, strictly outside the user's **approximately 11:46:24–12:16:24 UTC** requested window. The most recent returned motion event was **inactive at 11:33:47.069**, NOT a fresh report at request time. There were **zero reported motion changes in the returned page within the 30-minute window**, which is **not** proof that no motion occurred physically or that the sensor was continuously online.

**Additional provenance errors in first answer:** `event.type=physical` and `producedBy=Matter Aqara M3` are Hubitat/bridge metadata; they are **not independent proof that hardware initiated every transition**. Likewise, lack of commands in **motion device history** cannot prove that no controlling app or automation issued a command elsewhere; `triggered[]` lists apps listening to reports, not proven initiators. The answer's phrase “all transitions initiated by hardware” was unsupported. `historySourceIntegrityVerified=false`, despite `temporalAnalysis.coverage=complete` and `252s` for that broader returned hour. The latter is a **bounded 1-hour pairing analysis**, not proof of any 30-minute activity, exhaustive upstream source stream or actual human presence. This is a **failed first useful-complete answer** in the new sensor/event domain, not a cosmetic status-label problem. It also missed the charter's under-15s status target in this one sample.

**Claude qualitative comparison:** Later Claude answer said no motion events in the last 30 minutes and identified the 11:33:47 last inactive report; those central facts agree with HomeBrain's same read-only receipt chronology. Claude separately obtained driver configuration, parent Matter reachability, and app listener context, which were **not** independently provided as Claude tool receipts; do not count them as verified paired evidence or assert Claude parity/speed. Its description of Hubitat event type `physical` should still be qualified as a recorded classification rather than independent direct proof of physical detector action.

**General v0.18.359 correction (offline-tested only):** New `requested_event_window_evidence.py` interprets explicit rolling last/past/previous N minutes/hours/days from the **original user's request** and filters **already retrieved** successful typed `homebrain_device_history` event rows by independently saved receipt timestamp, keeping earlier observations as *context only*. It emits a short source packet just before the existing natural model final call. The packet explicitly distinguishes zero source events in the requested window from proof of no physical detection, and bridge reporter / `triggered[]` listeners from confirmed causality. **No additional MCP reads, model rounds, device writes, or hardcoded room-specific final text**. New frozen anonymous replay of the earlier 8 rows/252s / 1-hour-vs-30-min conflict requires **0 in-window**, **8 pre-window**, plus unrelated relative-time tests, invalid/malformed source and identity protections. No production Gemma adherence or actual speed improvement has been measured on v0.18.359.

**NEXT acceptance:** Preserve natural concise answer style. Once v0.18.359 is installed, ask **one fresh unrelated sensor/event-history read-only question** with an explicit **15–30 minute** window and send first answer + full Technical JSON. Verify that `requested_event_window_packet` was issued when typed history was available; count events using the user window rather than tool `hoursBack` and verify source `timestamp`, `effect`, `historySourceIntegrityVerified`, and event provenance. Record latency, model rounds and the user's own usefulness assessment separately. Do **not** retry Hallway FP300 to inflate a fixed-case success score; no further case-specific patches or live HA/Hubitat mutations.

## Live v0.18.358 Fridge acceptance — clock distinction VERIFIED (2026-11-02)

**NEW REAL LIVE BENCHMARK — no repository code changes:** User supplied first-run screenshot, complete Technical JSON and a later separate Claude narrative for a **read-only Fridge present-status + last-event question**. Installed version explicitly confirmed in request JSON: `0.18.358`; model `gemma4:31b` via Ollama Cloud free routing; `outcome=success` and green Success badge. **End-to-end 12,170 ms**, model provider 9,564 ms, **4 model rounds / 6 tool calls**, one discovery, one source-sufficiency stop, zero writes. Exact runtime `current_state_clock_packet=1`: the intended v0.18.358 final source timing packet **DID execute live**. This single sample is under the 15-second status goal; no matched-version speed or provider-token comparison exists and median/p95 remain NOT MEASURED.

**Independent receipts confirm answer's key facts:** deterministic resolver selected ID **7886 Fridge** and retained typed `switch=on`, `power=86 W`, `amperage=0.46 A`, `voltage=240 V`, `energy=237.816`, `telePeriod=60`, `healthStatus=online`, `deviceHealth=ok`, `mqttStatus=connected`, **driver-reported `lastSeen=Mon Nov 02 11:58:49 GMT 2026`**. Selected exact-source state still explicitly says `attributeChangeTimesVerified=false`. Separate read-only Fridge event-history returned **power=86 W at 2026-11-02T12:02:49.952+0000** and **switch=on at 2026-10-27T19:00:37.777+0000**. Source history integrity was flagged **unverified**, while selected bounded `observedEventsTruncated=false` for the narrow displayed event rows. The last actual state change across all possible missing sources remains unverified. **The natural response now correctly separates all three clocks** rather than treating the newest power event as `lastSeen`. It also avoids asserting physical compressor operation from an electrical watt reading. This is the first **confirmed live resolution** of the earlier v0.18.357 Freezer timestamp confusion.

**Answer review:** Direct, concise, first-attempt, correct reported values and per-attribute timestamps within the supplied source receipts. `Success` is appropriately not marked `Unresolved`. The caution “unknown if any switch transitions occurred between October 27 and the present” is conservative given `historySourceIntegrityVerified=false`; qualify as **not independently excluded by bounded source coverage**, not evidence that any further switch transition occurred. Subsequent Claude answer expanded 7-day history, 60-second power pattern, telemetry age and earlier off/on events; its raw source tool responses were not supplied, so these additions are not independently validated as a source-identical model comparison. **Do not attribute switch-event initiation to the named app merely because it appears in `triggered[]`: this is an event listener list, not proven command issuer.** Claude's “the switch has simply stayed on since” similarly goes beyond HomeBrain's bounded unverified history guarantee.

**Interpretation of progress:** The v0.18.357 real Freezer result verified correct typed receipt values but **incorrect lastSeen vs event association** at 15.642s / four rounds / four calls. The v0.18.358 Fridge first shot correctly separated the source clocks at **12.170s / four rounds / six calls**. These differ in target and query/history scope, so they are **NOT a controlled A/B** and their latency difference is not a measured speed gain. The installed v0.18.358 source-guidance change's core *functional temporal calibration* is nevertheless **verified in one live example**. The user's own usefulness rating for this specific answer was not separately solicited; the assistant evidence audit finds it useful, but official human-first-answer success rate remains **NOT MEASURED**. No live Hubitat/HA modification.

**NEXT charter milestone:** Stop accumulating status-specific patches after this verified success. Collect a few **independent read-only new-domain first shots** (e.g., a sensor active/inactive timeline, a scheduler decision, or a non-causal multi-device comparison) with exact receipts and elapsed times; score evidence-grounded facts and unresolved source classes explicitly. For status queries, monitor v0.18.358 p50/p95 and scope-specific token/model-round costs before further structural optimization. Preserve concise model-authored prose, current-source distinction and the observed under-15s individual performance. Do not repeat Freezer/Fridge/Washing Machine acceptance prompts as a substitute for domain diversity.

## v0.18.358 merged — real v0.18.357 Freezer source-clock assessment (2026-11-02)

**MERGED / exact-head ALL GREEN:** [PR #1286](https://github.com/ienam-smarthome/HomeBrainOS/pull/1286); tested head `8687def4cb3e5b560ae90cb8aa16358a228715c6`, merge commit `ddc868bea4d7ac2f209b3405c24eecb3e5095a16`. **7/7 GitHub checks success**, **5,777 Python tests, two warnings**, container smoke, metadata, both test and validate jobs. First head failed an output precision assertion and an unregistered metric counter; both fixed and full final exact-head rerun passed. **No live Hubitat / HA mutation.** New version v0.18.358 not yet live-evaluated or confirmed installed.

**Verified real Q3 sample:** User ran the first v0.18.357 Freezer status test and supplied actual screenshot + full Technical JSON and a later Claude explanation. Targeted device `7105` was exactly resolved; the `homebrain_resolve_device` evidence receipt now independently retained `power=0`, `switch=on`, `voltage=243`, `amperage=0`, `energy=604.958`, `lastSeen=Mon Nov 02 11:40:29 GMT 2026`, `mqttStatus=connected`, `healthStatus=online`. This **CONFIRMS** v0.18.357 source projection worked in the real add-on. The UI outcome was **Success**, not Unresolved, supporting the v0.18.356 causal-status completion fix in this case.

**Real correctness defect:** The natural answer correctly said that the smart plug reports `on` with zero W, but incorrectly called **11:44:24** the “last device check-in.” The saved **lastSeen** value is instead **11:40:29**. A separate 20-row bounded source event read included `power=0` at `11:44:24.221+0000`, `amperage=0` at `11:44:24.227+0000`, `voltage=243` at `11:44:24.223+0000`, and earlier `power=1` at `11:43:38.308+0000`. No switch event was among HomeBrain's returned bounded source rows; its true last switch change **was not established**. The source integrity flag for history was unverified and event rows truncated; do not promote these source reports to verified physical action. The user-supplied subsequent Claude answer used additional/later reads, including an alleged 27 Oct switch event, but Claude's complete raw receipts were not supplied; this remains a **qualitative** comparison, not an authenticated paired A/B.

**Actual runtime:** `elapsed_ms=15642`, provider 12.409s, four `gemma4:31b` Ollama Cloud model rounds, four tools, one discovery, no writes, Success badge. This single **15.642s** status observation is **0.642s slower** than the charter's 15s target; not median/p95 and not source-identical comparable to the earlier Washing Machine 12.255s. The main answer was useful but source-clock calibration was demonstrably wrong. Source value grounding for this particular selected-device packet was verifiable, unlike v0.18.355; overall model factual support rates NOT MEASURED.

**v0.18.358 general fix:** `current_state_clock_evidence.py` renders a short, source-scoped factual packet from the existing verified selected device and an optional same-target history event receipt, with explicit reported `lastSeen`, host read time and latest **returned** per-attribute event timestamp(s). A missing switch history means unknown actual last change, not “never changed”; unverified history event clock is not physical execution. The existing final model completion receives this packet with **no added tool calls or extra model rounds**, no name-specific heuristics, and no hardcoded answer replacement. Anonymous frozen-source tests cover the clock mismatch, missing and cross-device event history, failed/ambiguous identity, untrusted event strings, no invented times and final call integration. **Actual answer improvement/latency on v0.18.358 is NOT MEASURED.**

**NEXT:** Install v0.18.358 when available and run **one fresh, read-only current-state question about a different named device** with attribute timestamps (e.g. Fridge plug), taking the complete first answer and Technical JSON. Verify that Gemma correctly labels `lastSeen` and the latest matching attribute event as **different clocks** and does not assert the last switch change if a returned bounded page omits it. Record wall time, model/tool counts and user-rated usefulness; do not repeat Freezer and Washing Machine. If temporal distinction still fails, inspect how model synthesis prioritises the source packet before adding more tokens or filters. Keep under-15s status target; review actual latency impact rather than assuming neutrality.

## v0.18.357 verified merge — selected-device typed state evidence receipts (2026-11-02)

**MERGED / exact tested head ALL GREEN:** [PR #1284](https://github.com/ienam-smarthome/HomeBrainOS/pull/1284), tested head `600afc82ecc002b030ed649e11bdc73a3e1d5cf2`, merged commit `ff15198b11459c7832166ff57f2fa4703ef047a3`. **6/6 CI checks passed**: **5,770 Python tests / two warnings**, add-on container smoke, repository metadata and two validators. No live Hubitat or HA calls, mutations or settings changes. v0.18.357 has **not been verified installed**; most recent captured live add-on remains v0.18.355.

**Root cause fixed at the source:** The local named-device resolver had verified a selected candidate from up to two label-filter matches, but the `ToolExecutor` receipt saved a generic object-field summary, discarding its switch, power, energy and health values from Technical JSON. `current_device_receipt_projection.py` now exposes a small allowlisted, typed `reportedDeviceState.reportedAttributes` map on the **existing** `homebrain_resolve_device` receipt when source lookup is an exact name or direct verified numeric ID. Fuzzy, identity-fallback, unmatched, cached or mismatched-ID selections are not elevated to source attestation. No private logs, IP addresses, tokens, arbitrary strings or credentials retained; invalid/unsafe values are dropped. `ground_current_device_status` can inspect the selected resolver as a source and fails closed on conflicting earlier targeted lookup values. Normal model-authored prose unchanged.

**Timestamp meaning:** Receipt `timestamp` is the host's **read/recording instant**, not an individual attribute change. The reported `lastSeen` is a separate driver attribute, not proof that `switch` or `power` changed then. New receipt flags explicitly state `attributeChangeTimesVerified=false`, `readReceiptTimeIsAttributeEventTime=false`, and `physicalConnectivityVerified=false`. An absent attribute-specific event history does **not** prove no prior change; the actual last change remains unknown without a verified source record.

**Measured vs unmeasured:** Offline synthetic contract tests verify typed values, allowlist privacy, exact identity, stale/fuzzy denial, multiple-source conflict behavior, and clock distinction; no new tool/model calls were added in source. **NOT MEASURED:** v0.18.357 real produced Technical JSON, any live latency or first-answer improvement, per-attribute historical timestamp recovery, median/p95, model reasoning quality and source-identical Claude comparison. Earlier v0.18.355 real first attempt remains one user-rated useful 12.255-second sample (four rounds/four tools); not a matched version A/B.

**Next acceptance:** After installation, run one **fresh unrelated read-only** present-state question that identifies a device unambiguously, capture natural answer plus full Technical JSON, and verify `homebrain_resolve_device` receipt contains the exact ID and actual source-reported typed values. Check that the answer separates source read time, driver lastSeen and unknown attribute-change time without claiming physical execution. Where source is a broad/fuzzy identity or does not contain selected attributes, measure that the receipt is omitted rather than invented. No repeat of the previous Washing Machine query is necessary. If the receipt cannot be emitted on the actual common route, inspect the source projection in that route before extending it. Preserve the under-15s fast status target and do not add unnecessary model rounds.

## v0.18.356 verified fix and user-supplied Claude reference (2026-11-02)

**MERGED, exact-head ALL GREEN:** [PR #1282](https://github.com/ienam-smarthome/HomeBrainOS/pull/1282), tested head `19dab86c3ec8b1cbeeb6c00fdb54c1ead9af9d37`, merge SHA `e8f14e5a81b9fa428bb4c971ed61f8cedddfa7e1`. **7/7 GitHub checks passed**, full Python suite **5,761 passed, 2 warnings**, container, metadata, test and validations. First CI run failed an existing specialist telemetry source-calibration regression; the final fix explicitly preserves a previously established specialist domain even when the generic text classifier misses it. Latest exact head reran green. **Not yet installed or live-evaluated.**

**Generalized root cause:** A prior hypothesis-comparison coverage object triggered shared historical source-completion even for a factual current-status question. In `shared_investigation_completion.py`, the old noncausal early exit required `not isinstance(prior,dict)`; the fallback then defaulted `goal=None` to `causal_provenance`, mandating command history and marking a useful response `Unresolved`. The fix instead considers explicit user causal intent and an independently established specialist investigation domain. Non-causal current status with only candidate hypotheses no longer inherits historical command provenance. Real causal questions and domain-attested telemetry, rule, lockout, design and scheduler investigations retain strict coverage. No model/tool calls or live writes added; prose generation unchanged. Regression tests include status with hypothesis packet, cross-device factual comparison, generic specialized telemetry, actual why/off command provenance, and an explicit offline-telemetry contract.

**Claude comparison received after live first attempt:** User provided a separate, later Claude answer about the same appliance-status question. Claude led with switch=off/power=0 W, displayed health, amperage, voltage, cumulative energy and TelePeriod, separated check-in timestamp from unknown attribute-change timestamps, and reported having checked a 7-day event-history window with no switch/power/energy events. It qualified internal cycle progress, voltage/relay semantics, possibility of separate power path and history-completeness uncertainty. HomeBrain v0.18.355 delivered the main correct user-facing answer concisely at 12.255s; user rated it good. Its prose made an overly absolute physical-state claim and associated lastSeen freshness with individual values whose per-attribute timestamps were not exposed in the receipt export. **Claude's specific claims about 7-day history and last activity have not been independently validated against Claude's raw read receipts; its query was later, so this is NOT a source-identical model A/B or measured latency comparison.** Do not count Claude as objectively proven accurate, nor HomeBrain as a failed first answer, on this paired wording alone.

**Measured:** One user-rated useful first-attempt response on installed v0.18.355; one wall-time = 12.255 seconds; four model rounds and four tools; v0.18.356 deterministic source-completion regression green. **NOT MEASURED:** v0.18.356 live behavior, unbiased comparative answer score, provenance for each reported current attribute, model quality uplift, Claude latency, per-attribute event timestamps, production medians/p95.

**NEXT milestone:** Inspect and improve **typed per-attribute current-source projection and freshness semantics**, separating driver/host lastSeen heartbeats from attribute-change histories. Preserve bounded read-only source scopes, request-specific attribute selection and the fast status route; do not spend three extra reads unless source contracts justify them. Compare answer against actual matching typed switch/power/health/lastSeen values and attribute-specific timestamp availability, without inventing updates or interpreting no seven-day events as proven inactivity. Keep natural concise cause-first answer, optionally expandable richer evidence. Do not add case-specific appliance strings, rigid prose templates or an unmeasured Claude-parity claim. Live Hubitat/HA changes remain prohibited.

## First user-reviewed live response — current device status (2026-11-02)

**Observed and user rated:** v0.18.355, Ollama Cloud `gemma4:31b` free tier, initial question asking whether a named appliance was currently operating, asking for switch/power/timestamp and limits; user provided the **original first answer, screenshot and Technical JSON**. **User judgment: “answer looks pretty good to me”.** This is **1/1 user-rated useful first attempts in the currently provided live sample**, not an overall success-rate estimate, blinded human review, or proof of factual grounding. The reviewer corrected the initial over-strict “first-answer failure” assessment. Natural prose was concise, directly responsive, and appropriately distinguished prior cycle completion and internal programme unknowns.

**Measured first-shot runtime:** API elapsed `12,255 ms`, agent `12,222 ms`, provider `9,991 ms`, MCP `1,488 ms`; **4 Ollama model rounds, 4 tool calls, 1 discovery**, 0 state changes; version verified in returned Technical JSON. The under-15-second result is one observation, **not a median/p95**. The UI showed **Unresolved** and the shared completion recorded `shared_completion_partial=1`, `domain=causal_provenance`, required `command_history` unchecked, despite the question asking mainly for present status rather than identifying a historical command issuer. Investigate this metadata/goal mismatch separately; do not automatically label a useful status answer factually wrong due to a broader causal-completion rubric.

**Evidence audit limitations:** The retained device history displayed in the export is a three-row sample of `rssi`, `dataAgeSeconds` and `lastSeen` stamped 2026-11-02 11:02:38 GMT; target device lookup reports two candidates followed by a successful resolution but its exported receipt gives a field summary **without inspectable switch and power values**. The published answer says switch=off and power=0 W, **not independently confirmable from exported receipt details** (possibly supported by the full model-visible lookup; that raw content was not supplied). Do not claim those values fabricated. The phrase “physically impossible for a wash cycle to be active at zero W” is overly categorical: instantaneous 0 W does not establish wash-programme progress or all possible pauses/sensor limitations. Assert “reported switch off / power zero is consistent with not actively drawing power at the measurement” if the actual source is verified, while keeping cycle completion unknown. Fresh `lastSeen` and driver age alone are not independently proven physical connectivity.

**Honest review categories:** first-attempt usefulness = **user-rated yes (n=1)**; recorded duration = measured once; factual source support rate = **NOT MEASURED** due missing raw state values; unsupported definitive physical-state sentence = **flagged for review**, not a fully verified erroneous device state; causal initiator = not requested; model-to-Claude comparison = NOT MEASURED; reliability across devices = NOT MEASURED. No repeat query was required or performed. User feedback should outweigh a mechanical “unresolved” badge for **usefulness**, but it does not override missing source validation for **grounding**.

**NEXT:** Targeted read-only diagnosis of status answer completion metadata (why present-state request inherits `causal_provenance`/command-history), and whether source receipt projection can retain authoritative per-attribute switch/power value and timestamps without exposing secrets or requiring extra model rounds. Preserve the good natural-language answer; do not add device-name or phrase-specific corrections. Create a focused regression test or new PR only after confirming general source-level cause. No live Hubitat/HA modifications authorised.

## v0.18.355 verified merge — post-grounding read-source choice consolidation (2026-11-02)

**MERGED with ALL GREEN exact-head CI:** [PR #1279](https://github.com/ienam-smarthome/HomeBrainOS/pull/1279), tested head `0bce3da6ea9cd3fe47abc10c681a88e40a243dc2`, merged commit `fe68a4b824de9ef53aad7ef5960410e12da5436f`. All **6/6 check runs passed**: **5,756 Python tests / two warnings**, container smoke, metadata/import assurance and both validation workflows. First run caught two legacy text assertions of direct source-function calls; tests were updated to check the same source callbacks, source kinds and fixed priority. Final full exact-head rerun was green.

**Actual scope:** One reused `evidence_first_source_followup.py` selector now coordinates four post-grounding no-tool source proposals (diagnostic discriminator, necessary unchecked source, driver/controller and incident progress) in original priority order. The required-source candidate retains its current admitted read view and cannot expose additional gateways; other candidates retain the original read-only gateway set and catalog/effect checks. Each existing source-specific generator, attempted/verified read identity, `SourceCheckpointBudget` and source-specific flag/metric remains. Configuration semantics deliberately stays before grounding; semantic task coverage and causal provenance finalization remain outside the late candidate plan because they own distinct incompleteness/safety transitions. Model-written answers are not replaced or keyword-filtered; no live Hubitat or Home Assistant changes.

**Offline replay:** `tests/fixtures/q3_late_source_replay_v1.json` freezes 13 synthetic cross-domain source-choice cases. New offline tests compare independent prior-branch-order selection with the new shared selector on identical candidate prompts, admission flags and source-progress receipts (including checked-empty, unavailable, exhausted-budget and gateway-denial conditions). **13/13 source-choice matches** are an offline deterministic regression result, not a model-accuracy review or measured reduction in provider rounds. No real transcript or personal household data were fabricated.

**NOT MEASURED:** v0.18.355 actual live median/p95 latency, model/tool rounds, first-attempt usefulness, causal calibration, factual grounding, Claude parity or cost. The last independently observed installed version remains v0.18.348: 56.657 seconds, 11 rounds, 14 tools, with an omitted source-attested OFF command. Do not assert improvements in these metrics from CI alone.

**Next milestone (Q3 evaluation checkpoint, not more blind patches):** After multiple structural cycles, prioritise one NEW read-only HomeBrain first-attempt test in an unrelated domain on an installed v0.18.355 or later, capturing complete natural answer and Technical JSON including exact add-on/model/build, wall-time, model rounds, tool calls, receipts and source coverage. Compare evidence against its own first-shot data and the charter's rubric; mark unreviewed cases NOT MEASURED. Suggested distinct question: `Is Washing Machine running right now? Verify the latest switch and power readings and their timestamps, and explain what those reports can and cannot prove about the physical wash cycle. Read-only; do not change anything.` Avoid repeats of Bedroom 3 Mesh, Thermostat, bathroom lights/fan, Livingroom Light 2 and Dehumidifier 1. Additional late task-coverage/causal-provenance consolidation must be justified by reviewed quality/latency evidence, not assumed savings. The user has not authorized live Hubitat/HA mutation.

## v0.18.354 verified merge — one source proposal for early investigation checkpoints (2026-11-02)

**MERGED and exact-head ALL GREEN:** [PR #1277](https://github.com/ienam-smarthome/HomeBrainOS/pull/1277), tested head `17c8f3f65f745380006b51da465ffbcf566cbcc6`, merged commit `e712467d19ad2d6f81a27a8f8df48fd092d981d2`. **6/6 checks succeeded**, including **5,752 Python tests, two warnings**, add-on container smoke, release metadata/import assurance, validation and repository tests. Two earlier heads failed assertions expecting the separate inventory retry and direct progress-gate callsite; those tests were updated to assert the new shared plan while preserving the functional mock-agent inventory-only safety contract. The exact final head passed.

**Change:** v0.18.354 replaces three independently selected early no-tool source followups (target history, upstream input, inventory-only) with one `evidence_first_source_followup.py` priority selector and one scoped catalog/prompt execution path. The original admission generators still decide whether each source gap exists; precedence (target > input > inventory), v0.18.353 source-progress budget, read-only gateway constraints, honest partial inventory response, mandatory final source reconciliation and model-authored answer text are preserved. The read-only gateway names are explicitly allowlisted; no new tool privileges or live hub/HA actions.

**Frozen offline replay:** `tests/fixtures/q3_early_source_replay_v1.json` contains **8 anonymous synthetic source-choice inputs** with fixed prompts, admission flags and read-scope receipts. Tests compare a separate emulation of the former v0.18.353 independent branch order to the unified selection on the same packets. **8/8 cases match the former source choice**, and the test checks duplicate/failed source budget and lazy lower-priority evaluation. This is a genuine **deterministic selector-equivalence regression check**, *not* a paired model answer replay, real elapsed-latency measurement or accuracy evaluation.

**NOT MEASURED:** real model-round savings, median/p95 latency, factual grounding, unsupported causal claims, useful first-answer rate, comparative Claude quality, model/provider cost. The only verified installed run remains v0.18.348, Gemma Cloud, 56.657s/11 rounds/14 tools; no same-source user A/B on 0.18.354, and this release has not been verified installed on HA.

**NEXT unfinished Q3 milestone:** coalesce later independent no-tool candidates (configuration semantics, diagnostic discriminator, missing required source, driver/controller, incident progress, semantic coverage and causal provenance) into a receipt-grounded *single candidate/priority* plan placed **after** mandatory grounding and write-safety gates. Keep their source-specific feasibility, fallback and checked-but-empty distinctions. Before claiming a latency/quality uplift, use a model-level same-evidence replay or one fresh unrelated read-only HomeBrain first-run answer with Technical JSON after user installs an updated add-on. Do not repeat prior lighting/thermostat/fan/dehumidifier/MQTT acceptance cases; no live mutation authorized.

## v0.18.353 merged — one evidence-progress gate for overlapping no-tool recoveries (2026-11-02)

**MERGED / exact-head ALL GREEN:** [PR #1275](https://github.com/ienam-smarthome/HomeBrainOS/pull/1275), merge commit `69848b19d0cd67555f8f83cb84eb3985775fa9e6`, exact tested head `5cb4d864740f9fe6c8472996e2f4f8405c61159c`. **7/7 checks passed**: **5,747 Python tests, two warnings**, add-on container smoke, metadata and validation checks. The merged version is **0.18.353**; installation on the user's HA system is not verified.

**Scope:** The request-local `SourceCheckpointBudget` now coordinates ten no-tool source-choice recovery paths in `mcp_agent_orchestrator.py`. A further checkpoint needs a new successful distinct read-only tool/argument scope; failed, duplicate or write-class receipts cannot renew it. There is a three-offer request-wide ceiling. Existing source-specific evidence admission, provenance, model tool calls, journal host recovery, mandatory final answer evidence reads, confirmation/security guardrails and natural model-authored explanations remain. The existing shared `evidence_first_checkpoint_plan.py` is reused; no additional planner stack or device-specific content patch. Tests cover no-progress, repeated scopes, successful new history/app-log scope, failure, write, cross-request isolation and gating integration.

**What is measured:** The *synthetic/offline admission behavior* and existing regression suite passed. **NOT MEASURED:** production Ollama round count, elapsed latency, human first-answer grounding and causal-calibration success, false negatives from the new budget or any Claude gap. The only verified installed baseline remains v0.18.348 (56.657s, 11 rounds, 14 tools) with one missed recorded OFF command; it is not a same-evidence before/after benchmark for this release. Do not label 0.18.353 faster or more accurate based solely on CI.

**NEXT Q3 milestone:** Extract the remaining independent source-candidate generators into **one evidence-first source obligation proposal/priority plan**, rather than just shared retry admission, and run offline *same-packet* before/after model-round/source-completeness replay. Preserve source classes when a result was checked-but-empty or unavailable and keep natural explanation plus causal uncertainty. Do not request repeats of Bedroom 3 Mesh, Livingroom Light 2, Thermostat, Fan Boost or Dehumidifier 1. After an objectively reviewed frozen-source baseline or fresh unrelated first-run read-only HomeBrain question, assess the actual quality and latency tradeoff. Never change live Hubitat/HA without specific authorization.

## v0.18.352 verified merge — first shared evidence checkpoint selector (2026-11-02)

**MERGED; exact-head ALL GREEN:** [PR #1273](https://github.com/ienam-smarthome/HomeBrainOS/pull/1273), merge commit `da3e1d73e88b2985cbbbcfbd180566d1feba1e89`, exact tested head `161565adf4903a3d0f21de0d92da55ce0f154a85`. All **7/7** latest head check runs succeeded: full Python suite, add-on container smoke, metadata and validations. Earlier CI attempts caught missing release/module documentation and an unintended fallback issuer-planner invocation; all were fixed and retested before merging.

**Scope:** Added `evidence_first_checkpoint_plan.py` with pure, deterministic, read-only source-checkpoint priority selection and offline tests for stable ordering, unsuccessful/unverified/unsafe candidate rejection, previous-attempt exclusion, and no input mutation. Existing `source_obligation_coordinator.py` now uses this selector for its verified issuing-app source, preserving incident-time historical priority and short-circuiting the fallback model-command planner. **This is the first Q3 production integration, not the finished unified multi-round planner.** No live hub, automation, Home Assistant configuration or permissions changed. No answer-prose template added.

**Measurement:** Frozen-source human factual quality, Claude gap and v0.18.352 live latency **NOT MEASURED**. Regression green is not an answer-quality score. The only real baseline recorded remains v0.18.348 Dehumidifier 1 (56.657s, 11 rounds, 14 tools), which should not be repeated immediately. Do not claim v0.18.352 shortened model rounds. Add-on update/installation is user-controlled.

**NEXT unfinished Q3 milestone:** Inspect `mcp_agent_orchestrator.py` no-tool path and fold target-scope, unified-input, inventory-only, configuration-semantics, telemetry/checkpoint, task coverage and other overlapping recovery rounds into **one receipt-grounded bounded read-plan coordinator**, preserving each source's admission and unavailable-source caveats. Use offline frozen-source traces for before/after source-call/round-count and safety checks, then a fresh unrelated read-only first-run user Q&A only when necessary. Do not restart roadmap or add device-specific wording patches. Update this handoff after exact-head CI-verified progress.

## v0.18.351 verified merge — coalesced source read finalization (2026-11-02)

**MERGED and exact-head ALL GREEN:** [PR #1271](https://github.com/ienam-smarthome/HomeBrainOS/pull/1271) merged as `bb721664e64b0b2a58a2c0e7409c7f62f0b04a15`; tested head `adb62ca4f05708cbbd599d34e6453c1e6a8b7523`. **8 of 8 checks succeeded**, including **5,735 Python tests, two warnings**, add-on container smoke, metadata validation, offline scorecard and CI validations. One request-local, lazy finalization tool catalog now replaces repeated `mcp.list_tools()` calls for device logs, scoped config, required command history and issuing-app decision logs. One pure selector prioritizes a source-proven historical incident's issuing app, falling back to a general typed-method command witness. One read-only execution path handles live gateway schema and effect admission, with existing confirmed device IDs, app IDs, bounded clocks and failed-retry guards retained. No device/automation writes, no new model round, no final-answer replacement template.

**Production limits and measurement:** `0.18.351` is **merged but not independently installed or live-tested**. The only verified latest installed trace remains v0.18.348 from Dehumidifier 1: 56.657s/11 Gemma rounds/14 tools, with an observed OFF command omitted from prose. v0.18.350 reconciled that source discrepancy, but both live uplift and source-call savings from v0.18.351 are **NOT MEASURED**. Exact-head green CI demonstrates regression health, not factual/Claude-like parity. The **remaining next milestone** is moving overlapping earlier model-selected and host recovery/checkpoint read plans into one bounded evidence-first planner, with frozen-source before/after safety and answer-quality evaluation. Do not request repeats of previously overtested Bedroom 3 Mesh, Livingroom Light 2, Thermostat, Fan Boost or Dehumidifier 1. Only use fresh cross-domain first-run tests when source verification is necessary.

## v0.18.351 generic read-obligation consolidation candidate (2026-11-02)

**Actual repository code inefficiency:** In `mcp_agent_orchestrator.py::_final_answer`, source completion independently re-fetched the same live MCP capability list up to five times (device logs, targeted configuration, historical command history, historical app-producer decision logs and typed-method app-producer decision logs). The final two paths implement overlapping app-log obligations and separate execution/permission/error handling, although both require source-proven issuing apps. This creates redundant schema checks/host orchestration; depending on model tool history, finalization might perform both app decision reads for one incident. This is a **source-planning design issue**, not a device-answer string defect.

**v0.18.351 candidate changes:** Add pure `source_obligation_coordinator.select_issuing_app_log_obligation` with one verified app-log plan (historical source-time clock precedence; fallback to general typed method source); no inferred app ID or new permissions. Execute once through existing read-only gateway with scope, schema, and effect checks, retaining legacy metrics plus two source-plan counters. Cache the request's *live capability catalog once* and reuse for device logs, configuration, command history and selected app log. Preserve the earlier app-log source planners as strict evidence admission rules, including no repeat after attempted failures. No new model round, no host prose replacement, no Hubitat/HA changes. Synthetic tests check historical priority, normal method fallback, verified identity and no reattempt after failure.

**Measurement:** The real first-shot v0.18.348 Dehumidifier 1 comparison remains 11 rounds, 14 tools, 56.657s and one missing OFF attribution. v0.18.350 has no live assessment yet. v0.18.351 source-catalog/repeated decision-path savings are structural **hypotheses**, not independently observed latency or accuracy improvements; no Claude-parity claim. A single general source-first planner for pre-model collection, model round caps and recovery still remains the broader milestone after this smaller bounded consolidation.

## v0.18.350 exact-head merged and verified (2026-11-02)

**MERGED and verified:** [PR #1269](https://github.com/ienam-smarthome/HomeBrainOS/pull/1269) merged as `030b17a1629d428a166a02cf2a908061b1309005`. Exact verified head `35ae2b60b74caa6195a8539a990b5caada77f991` passed **all eight check runs**, including **5,730 Python tests / 2 warnings**, add-on container smoke, release metadata, offline scorecard and validation pipelines. The first run caught an ID mismatch regression: a targeted lookup's wrong ID could be paired with same-named deterministic history. Corrected by requiring a **separately successful native history with the identical device ID** before publishing a reconciled packet. Final exact-head retest all green.

**Actual scope:** One new read-only, request-local `focal_event_reconciliation.py` packet. It combines bounded native ID-scoped and corresponding label-scoped `observedEvents` and `events` across overlapping pages, projects both command directions, explicit command issuer app IDs, switch ON/OFF timestamp differences and discrete power reports, keeps truncation and missing-history caveats. The packet is provided to Gemma after narrower source packets and in Technical JSON `reconciledFocalEventEvidence`. There is **no host answer rewrite**, no new MCP requests, no model/permission change and no Hubitat/HA mutation.

**Verification limits:** Tests show evidence can be correctly reconciled and supplied, NOT that Gemma will obey every factual boundary. No user-run v0.18.350 answer or frozen-source A/B yet; **user-perceived accuracy, latency and Claude parity NOT MEASURED**. Do not ask for another identical Dehumidifier 1 test; prior Bedroom 3 Mesh, Livingroom Light 2, Thermostat and Fan Boost repeats remain out of scope. The next engineering milestone remains unified source-first read planning and reducing overlapping provider/tool rounds, not a further case-specific string filter. New first-shot user test should target an unrelated domain only when useful.

## Cross-domain Dehumidifier 1 first-shot v0.18.348 — source found, answer missed it (2026-11-02)

**REAL live user-run first attempt, 2026-11-02 08:26–08:27Z:** Add-on `0.18.348`, `gemma4:31b` Ollama Cloud free, **56.657s total / 54.484s agent; 38.095s provider; 11 model rounds / 14 tools**. One uniquely verified device ID **5313** with label Dehumidifier 1. Recorded main switch ON at **2026-11-01 16:31:23.288Z**, OFF at **18:07:35.273Z**, about 1h36m12s ON-reported interval. An explicit `command-on` from app 3995 at **16:31:23.210Z** was found via a final `attribute=command-on` request. More importantly, a successful **earlier native ID-scoped all-attribute** history from 16:00–19:00 contains explicit `type=command`, `name=command-off`, `date=2026-11-01T18:07:35.001Z`, `producedBy:{name:"01. Humidity Controller", appId:3995}` — **272 milliseconds before** the state OFF report. Despite this direct source, the final answer says **'no explicit command-off event was recorded'** and that the OFF issuer is unknown. Both ON and OFF *recorded issuing app* IDs are therefore established, but the controller's *reason* for turning the switch OFF is not. A bounded `hub_get_logs(appId=3995, since 18:00, until 18:15)` was retrieved, but the returned metadata alone do not provide the app's decision reason. Coverage is partial and source integrity unverified. **Major omission/contradiction FAILED**.

**Power chronology, separate from switch runtime:** Same bounded source has reported power **0W at 18:07:06.633Z, 88W at 18:07:08.127Z, 81W at 18:07:36.137Z, 0W at 18:07:38.130Z**. That 16-row all-attribute window was `observedEventsTruncated=true`; earlier 18:03:33 amperage/powerFactor and 18:05 energy existed. The model falsely claimed 16:31–18:07 was **3.5 hours** (actual ≈1h36) and that the earliest *returned* nonzero power sample proved the **first actual physical operation**, asserting only 30 seconds of real use. The data support only those *specific reported samples* and the bounded switch interval, not appliance compressor start or total physical run duration. **Factual accuracy FAIL** despite improved model prose and positive source retrieval. The same v0.18.348 answer takes 14 tools/11 rounds, exceeding <45s preferred latency; no latency improvement from later v0.18.349 can be asserted without comparable live trace. Do not repeat this exact device as an immediate acceptance question.

**General next change v0.18.350 candidate:** The source pipeline delivered separate overlapping native and projected event pages without a consolidated truth-preserving latest-cycle packet. Introduce **one request-local cross-source reconciliation** for a uniquely and exactly verified target ID/label (no guess or fuzzy routing), accepting only successful nonmutating native device-ID-scoped or same-label deterministic histories. Source-positive facts include both filtered `details.events` and unfiltered `details.observedEvents` command types, actor IDs only with positive app-typed provenance, UTC source-timed switch events and sampled power values. Calculate a bounded **reported plug ON-to-OFF interval**, explicitly *not* physical appliance runtime; preserve truncation and source-completeness warnings. Feed this concise reconciled evidence to existing model writer and Technical JSON. Do NOT invent a word-level answer blacklisting patch, do NOT remove model-authored natural prose, do NOT query live Hubitat/HA for development, and do NOT relax write safety. Offline fixtures replay one native OFF command alongside later filtered ON command and power samples. The programme's official independent model-quality score remains **NOT MEASURED** until a fresh human source-grounded review.

## v0.18.349 verified merge and next general efficiency target (2026-11-02)

**MERGED / CI VERIFIED:** [PR #1267](https://github.com/ienam-smarthome/HomeBrainOS/pull/1267), merge `a713d914dd3969e9b6a8f58b6a3278bdb2574571`, exact tested head `eb9a0164a297925389435544ff6ef116715adcf4`. **All eight check runs green**, including **5,725 Python passed / 2 warnings**, add-on container smoke, release metadata, offline scorecard integrity and validation workflows. Only native-location-event versus local-wrapper same-window source re-use was introduced; all target device histories, longer pages, scope filters, app logs and control paths retain their previous behavior. No change to live Hubitat/HA.

**Rollout and measurement:** This is the first bounded source-reuse component; **no live A/B or measured speed improvement**, and does not meaningfully claim to resolve 11 model rounds/19 tools. User was instructed to first run one unrelated Dehumidifier 1 ON-to-OFF diagnostic on v0.18.348 and return its first answer/Technical JSON before moving versions, to preserve a clear baseline. Do not claim a test result before it arrives. Next development is evidence-driven single-plan orchestration to stop overlapping host retry machinery and broad reads, preserving source classes and the natural model writer. Zero-definitive-unsupported-cause charter target remains unmet. Do not repeat prior MQTT, lighting, heating or fan incident tests.

## v0.18.349 first source-reuse consolidation candidate (2026-11-02)

**Question/test issued to user on installed v0.18.348:** "Investigate the most recent complete ON-to-OFF cycle of Dehumidifier 1. What caused ON/OFF, which app issued commands, check power and decision logs, distinguish recorded commands/state from physical operation. Read-only." This is a **new cross-domain, first-shot** test; no answer or Technical JSON has yet been returned. Do not count it as an evaluation until reviewed.

**Repository evidence-derived optimization:** Previous v0.18.347 Fan Boost source receipts included a native `hub_read_devices.hub_list_device_events(hoursBack=48,limit=20, no target)` location-event page and a subsequent `homebrain_location_events(hours_back=48)` projecting the same bounded page. The second source had no distinct scope. Proposed `source_read_reuse_policy.py` provides a general request-local source obligation equivalence check for that single read class, after the first native read **succeeded**. Suppresses only an equal or smaller, unfiltered local location projection. Preserves the first source model context; never blocks device-ID-scoped histories, filtered location event histories, longer/larger pages, app logs, broker queries, control/write calls or a first attempt. No change to natural prose publisher, source truth/calibration, provider budgets or permissions. Synthetic tests replay the source contract and fail-open guards; **not an independent measurement of speed/accuracy**, and cannot claim the 66-second Fan Boost run will be faster by any specific amount. The fuller single evidence-first plan remains future work. No live Hubitat/HA changes.

## v0.18.348 verified merge and next development target (2026-11-02)

**MERGED and exact-head CI GREEN:** [PR #1265](https://github.com/ienam-smarthome/HomeBrainOS/pull/1265) merged as `badbecd24cbbcda2be10e6d78a02bfadf20f407d`; exact tested head `e4e9dedb367f21ec16d966b8b1d014f6c5ac81e6` passed **all eight checks** (full Python suite **5,721 passed, two warnings**, container smoke, release metadata, scorecard integrity, both validation pipelines). Verified one source-identity source-contract PR, not a general publisher redesign. No live Hubitat, Home Assistant, rule, manual override or storage mutation.

**Actual impact remains unverified:** User has not yet installed v0.18.348; no comparable frozen-source first-answer A/B, and no measured factual accuracy gain. The most recent installed real result remains v0.18.347's 66.506-second/11-round/19-tool Fan Boost read, with an app-issued command supported but source-proven internal scheduler decision absent.

**Next developer milestone:** Reduce redundant broad/unrelated reads and overlapping retries across incident scopes using one bounded source-obligation plan and offline replay, without sacrificing the already-attested command history and without adding domain-specific answer templates. Prioritize fewer model rounds and reliable first-answer source coverage. Do NOT ask the user to rerun Bedroom 3 Mesh, Livingroom Light 2, Thermostat, or Fan Boost immediately. Further user acceptance should be a fresh question in a distinct domain after the efficiency work is independently verified. Continue to flag Hubitat backup failure (938 MB free vs >=1GB requirement) as separate user attention, not a programming-side deletion action. Overall score and Claude parity NOT MEASURED.

## Fan Boost first-shot diagnostic: strong commands, missing decision source, long latency (2026-11-02)

**Live installed v0.18.347 result:** A single read-only first-shot bathroom ventilation fan question returned in **66,506 ms** total (65,245 ms model phase; 56,297 ms provider); **11 Gemma 4 31B Cloud rounds, 19 tool calls, 1 discovery**. Device was positively identified as `Fan Boost` ID 7850, its model-sourced question phrase was 'bathroom ventilation fan'. Independently bounded native history and deterministic source presentation recorded `command-on` produced by `01. Humidity Controller` App 3995 at **2026-11-01 21:59:59.941Z**, followed by Matter SwitchBot Hub 2 switch ON report at **22:00:00.261Z**; app `command-off` at **22:30:00.036Z**, followed by bridge switch OFF report at **22:30:00.666Z**. Reported ON interval ≈30m. Other observed cycles 04:00–05:30, 07:00–07:30, 12:00–12:30, 16:31–18:08. Partial event coverage, source completeness unverified, first 20-row mixed history truncated. Configuration from `hub_get_app_config(appId=3995)` and `pageName=unitPage4` was reportedly consistent with scheduled 22:00 / 30m; source attests app issuer, not that scheduler's internal trigger fired. Humidity 54% at 21:30 and 56% at 22:30 cannot exclude readings/threshold crossings in between; the 16:31–18:08 cycle coincides with later reported values 80/74/68% and is a separate event.

**Review:** Most likely scheduled event based on precisely matched timing and recorded controller; **'Scheduled Cycles (Confirmed Trigger)', 'Humidity Ruled Out' and 'Manual Override Ruled Out' are unjustified definitive claims** without contemporaneous app decision logs and/or complete relevant sensor/manual histories. No `hub_get_logs(appId=3995)` present, `hypothesisComparisons[].app_logs.source_state=source-class-not-checked`. `sourceCoverage.sourceKindsChecked=true` for device_history+command_history only; it does not establish schedule trigger. `rootCauseVerified=null`, `causalInitiatorVerified=null`, `evidenceComplete=false`, `outcome=unresolved`. Two irrelevant or low-yield global location events reads included `TV_Minutes_Used` variable updates; 19 tools/11 model rounds violate complex-investigation preferred <45s. Model was fluent but falsely converted command+schedule correlation into proven cause. **First-shot causal factual grounding FAIL / source collection stronger than earlier domains; latency FAIL.** Formal controlled answer-quality score remains NOT MEASURED.

**Secondary independent safety observation:** Three 2026-11-02 00:12Z location events from Hubitat explicitly record `localBackup=FAILED` because full backup requires >=1GB free, only **938MB** available. This was surfaced to user as a storage/backup warning; **no backup deletion or hub maintenance authorized**.

**General root mechanism and proposed v0.18.348:** The generic typed-command source method required exact user-string match of the Hubitat device label for app-log completion. Request said 'bathroom ventilation fan', yet successful unique targeted device lookup and command events bound ID 7850 to label 'Fan Boost'. Enhance the existing shared contract to admit a *uniquely* ID-scoped target with a matching successful deterministic resolution request, successful native device event-history source, and a device-label token contradiction check. Reject multiple targeted devices, mismatched IDs, missing history, unresolved target or explicitly contradictory compound names. This permits one already-authorized, single-attempt ±10-minute app-ID-scoped read if live gateway permits; **does not grant model new tools or write authority**. Explicit model source packet should distinguish scheduled-time correlation from verified app decision, and sparse sensor readings from a ruled-out alternative. This is one small generalizable source identity fix, **not another case-specific answer template**. The bigger cause of slow 11-round/19-read runs remains overlapping planners and needs separate unified read-plan refactor. No repeat of current fan case as immediate benchmark; choose distinct future first-shot question only after source quality assessment.

## v0.18.347 verified code merge and cross-domain acceptance (2026-11-02)

**Verified merged source:** [PR #1263](https://github.com/ienam-smarthome/HomeBrainOS/pull/1263) merged as `c71016ff12c047c61ef7b7afbc9c5fee59090406`. Exact head `c7e7330e0263d05bd536c08e19c3a24620ed5086` passed **8 of 8 checks**, including **5,719 Python tests**, metadata/repository validation, add-on container smoke, scorecard integrity and the validation workflows. Initial and second CI attempts failed a generic ambiguous-short-label test because a device name could match a different compound name, and its regex word boundaries had been incorrectly escaped. After conservative target-label admission and correcting regex escapes, full exact-head rerun was all green. These checks verify code health, not model factual accuracy. No live Hubitat/HA changes.

**Production change:** Positive source-scoped `command-setThermostatMode` and other offset-aware method commands now count as command-history evidence, distinct from unverified upstream triggers and physical operation. The source packet and Technical JSON `observedMethodCommandEvidence` preserve recorded issuing app and command time without declaring the reason. For requests seeking causality/protection/scheduler decisions and a unique attested device label, the host can attempt one read-only `hub_get_logs` for the observed issuing app, using a ±10-minute window and live effect/schema gate. The question's device name must be unambiguous; compound shorter-label matches fail closed. Existing model-led natural answer path, permissions, confirmations and device controls unchanged. This does **not** verify current Early Heating OFF/protection state or boiler actuation.

**Next user test: NEW DOMAIN, first attempt only.** Install v0.18.347; ask once: "Investigate why the bathroom ventilation fan most recently used boost mode. Compare reported humidity, its thresholds and holds, scheduled cycles, night mode and any manual FanBoost override. Identify the actual recorded controlling commands and any app decision logs, distinguishing source reports from verified triggers. Explain the best-supported reason, any evidence gaps, and do not change anything." Capture full answer + complete Technical JSON. Do not retest Bedroom 3 Mesh, Livingroom Light 2 or Thermostat as the immediate acceptance exercise. Model accuracy gap remains NOT MEASURED; the architectural milestone beyond this remains a single unified source-first investigation planner and source-proof benchmark.

## First live heating-domain test on v0.18.346 (2026-11-02)

**Source-bounded first attempt:** User-run read-only investigation of current main Thermostat, TRVs and scheduler/protection. Installed `0.18.346`, Gemma Cloud `gemma4:31b`, 6 rounds, 10 tools, **31.047 seconds** elapsed (28.623 seconds agent phase, 23.982 seconds provider). Hubitat reported main Thermostat (4382) `thermostatMode=off`, `thermostatOperatingState=idle`, temperature 21.0 °C versus heat setpoint 12.0 °C. Sampled five TRVs all above their reported 16.0 °C setpoints. Source-timed event history has `command-setThermostatMode(off)` at `2026-11-01T22:30:02.397+00:00`, `producedBy:{type:app,id:2710,label:Heating: Thermostat OFF}`, and the device's `thermostatMode=off` state report at `22:30:02.791` (+0.394s). This supports a recorded app command preceding a reported mode change but **not** proven physical boiler shutdown or the app's upstream reason. No scheduler `hub_get_jobs` or targeted app-decision logs were read. App 3970 config was read but its settings are insufficient as proof of current protection/override state; the app config excerpt was truncated. Model nonetheless inferred all room-demand conditions and a specific OFF reason, claimed no heat command had been issued, and treated protection/early override as effectively inactive. The technical contract marked `sourceCoverage.missingSourceKinds=["command_history"]` despite a typed non-ON/OFF command event in the 14-row scoped history. `causalInitiatorVerified=null`, `evidenceComplete=false`, `historySourceIntegrityVerified=false`. **Heating first-answer completeness/causal accuracy FAILED; useful current OFF status only.**

**Generalisable v0.18.347 candidate:** Extend source-class coverage to typed, offset-aware method commands `command-setThermostatMode`, `command-setLevel` etc. from a native ID-scoped or uniquely label-scoped successful history. The explicit `producedBy.type=app` numeric ID identifies a recorded issuer, not a scheduler trigger. Feed a bounded source-role chronology to the model without replacing prose. When an issuer ID is explicitly observed and the user requests causal/scheduler/protection explanation, attempt at most **one** read-only `hub_get_logs` window (±10 minutes of latest observed command) for that verified app; the gateway may legitimately reject it and the answer must retain that uncertainty. A command source class is not proof of command history completeness, physical boiler activity, protection state or scheduler decision. No user device/HA mutations, no extra Gemma round; extra MCP read may affect latency. Full planner consolidation remains the long-term architectural task. Next different-domain acceptance is fan boost, not another repeat thermostat question. The real model quality scorecard is still NOT MEASURED.

## v0.18.346 verified merge — general command-history source completion (2026-11-01)

**MERGED & CI VERIFIED:** [PR #1261](https://github.com/ienam-smarthome/HomeBrainOS/pull/1261) merged as `9e599480764d21c0fa00846aeb63a1072006a2d6`. Exact tested head `daa6b1500ac3645acbdc594e292880e4a424d164`: **all seven GitHub checks succeeded**, including **5,714 Python tests**, container smoke, release metadata, scorecard integrity and validation. First run caught a regex escaping bug that prevented the new source packet from matching a requested ON/OFF action; corrected and fully retested. No live Hubitat or Home Assistant changes.

**What changed:** Recent last-event ON/OFF causal questions can now complete the existing missing read-only command source using the uniquely verified device ID/label, matching observed switch boundary and actual lookback. It executes at most one target-scoped `command-off`/`command-on` history request and never guesses a driver ID or command issuer. A typed `recentCommandIssuerSource` records if the source was checked and if a positively sourced command event with issuing app exists; the model receives the same source-role distinctions before authoring natural prose. Post-report log completion, bridge-produced state, downstream event listener IDs and mere proximity are **not** command issuer proof, and even a direct command receipt cannot prove physical cause. Existing controls, confirmation permissions and model-first telemetry flag are untouched.

**Quality limitations:** No same-source live comparison was run on v0.18.346. All checks green proves implementation health, NOT factual accuracy or usefulness. Do not claim that this source completion solved every causal question. The full orchestrator still has overlapping reads and separate planners. The charter's zero-unsupported-definitive-causes target has not been reached.

**NEXT FIRST-ATTEMPT read-only user test — different domain, heating:** "Investigate why the main Thermostat is currently heating or requesting heat, considering current room temperatures, heating setpoints, multi-room demand coordination, any active 45-minute protection, Early Heating OFF, and the scheduler's most recent decisions. Separate observed thermostat/TRV states from issued commands and proven boiler operation. Explain the most likely reason and what remains unverified. Do not change anything." Capture the complete answer and Technical JSON, with model/version, source reads, causal attribution and elapsed. One test only; do NOT rerun Bedroom 3 Mesh or Livingroom Light 2 for this acceptance gate. After heating, evaluate bathroom fan FanBoost/humidity/manual/schedule path. Quality scorecard remains NOT MEASURED until human source verification.

## Cross-domain first-shot review: most recent Livingroom Light 2 OFF (2026-11-01)

**Real user-run v0.18.345:** Gemma 4 31B Ollama Cloud, 6 rounds, 11 tool calls, **31.5s**. Target device 7828 ON `2026-11-01T22:49:53.082Z` and OFF `22:50:00.647Z` are recorded Hue Bridge reports. A purported MCP Rule Server App 4151 device-command completion log was reported at `22:50:01.236Z`, **589ms after** the OFF report. No typed target-scoped `command-off` history read occurred: Technical JSON `sourceCoverage.missingSourceKinds=["command_history"]`, `causalInitiatorVerified=null`, `evidenceComplete=false`. A post-report completion cannot by itself establish whether/when an OFF was issued or prove it caused an earlier report. The off-light listener App 4020 and other triggered subscribers are not initiators by virtue of notification. Nevertheless the model pronounced App 4151 the controlling initiating cause. **First-attempt factual attribution FAILED; natural wording alone is not success**. Model source receipts contained no independent app/sensor trigger decision. Some generic hub logs were queried twice in overlapping windows; privacy-safe receipt summaries do not preserve their full content.

**Generalizable root defect:** The existing host command-history completion policy only admitted dated questions or ones including a literal numeric device ID. Ordinary latest-event questions with a resolved device label thus bypassed the required scoped command stream. Model then promoted nearby generic log completion to an issuer/cause. **v0.18.346 candidate** extends the existing command-source completion step to latest single-target ON/OFF causal requests with verified identity and observed focal switch state (no dates, no guessed IDs). One source read per action/device, no duplicate retry, no new MCP privileges, no additional model rounds. Typed recent issuer source packet and diagnostics keep bridge/handler/command/log roles separate and refuse to mark causal effect verified from timestamp alone. No room-specific phrases or replacement answer templates. Source accuracy improvement and overall benchmark still **NOT MEASURED** until a different-domain first-try test; do not repeat Bedroom 3 Mesh or overfit this event.

**Next:** exact-head CI/metadata/container, merge only ALL GREEN, then assess heating scheduler or fan boost instead of a repeat lighting run. A unified read planner across domains is the larger remaining architectural task.

## v0.18.345 verified release — restored earlier behavior (2026-11-01)

**MERGED AND CI VERIFIED:** [PR #1259](https://github.com/ienam-smarthome/HomeBrainOS/pull/1259), merge SHA `b380b3ff8cf1ef7d6a852dcc4391b1df34b4c136`. Exact tested head `65827c4c44b0e6aed3fe471f0b0717f2dc0c0c26`: all **six** GitHub check runs succeeded, including **5,705 Python tests**, metadata/repository release validation, add-on container smoke and offline scorecard integrity. Verified the six runtime modules each matched their v0.18.343 versions byte-for-byte. New v0.18.345 regression test verifies source-clock conflict alone no longer forcibly replaces careful model-authored prose. `model_first_investigations_enabled` remains off by default, and command/device write gates remain unchanged.

**User direction is binding:** Do NOT ask Bedroom 3 Mesh question again or continue case-specific rule patches. Test different domains **one question per first attempt**, starting with the most recent OFF event of Livingroom Light 2 (issuer versus Hue bridge reporter), then thermostat heating protection/scheduling, then FanBoost humidity/schedule/manual source. Require answer plus technical evidence; score honest factual grounding, confidence calibration, useful explanation and latency. This release is a user-preferred presentation rollback, not a claim that previous MQTT conclusions were source-verified. Next architecture focus remains the single planner and cross-domain quality gate.

## v0.18.345 requested behavioral rollback and cross-domain acceptance (2026-11-01)

**User decision:** Stop repetitive Bedroom 3 Mesh testing. The v0.18.344 reply was accurate about source uncertainty but reverted to the rigid host-authored presentation; the user explicitly prefers the earlier model-led style and requested the previous behavior be restored. **This is a presentation preference, not proof that v0.18.343's active-broker/LWT claims were correct.** The previously supplied v0.18.344 actual trace confirms `version=0.18.344`, `elapsed_ms=25565`, `model_rounds=5`, `tool_calls=7`, and `modelFirstRejection=unresolved-source-clock-conflict`; `publishedIsFirstModelDraft=false`. Driver config code metadata remained `unverified`; no source chunk or independent broker observation was returned.

**v0.18.345 rollback:** Restore the six runtime modules altered by PR #1257 to their exact v0.18.343 code, remove the v344-only source-ID test, retain v0.18.343 source-authority envelope and bounded configuration read, and remove v344's automatic contradiction-triggered source-template replacement. Publish under a **new version number** for normal HA add-on updates. The original opt-in `model_first_investigations_enabled` setting remains **off by default**. Preserve all write permission and confirmation boundaries. A new generic regression test checks preservation of a cautious unchanged model draft when source clocks disagree; this test does **not** certify fact accuracy.

**Next evaluations: one-shot, distinct, read-only domains.** Prioritize (1) Livingroom Light 2 most recent OFF: distinguish actual commanding app from bridge reporter and correlated sensors, (2) main Thermostat/room TRVs: explain current heating protection and schedule decisions without changing setpoints, (3) bathroom fan FanBoost: source-grounded most recent boost decision, manual/schedule/humidity distinction. Collect the answer and Technical JSON for each separately; no repeat retries or user-side network commands. Measure source coverage, first-answer factual accuracy, natural explanation and latency. Scorecard currently **NOT MEASURED**. Do not present new work as finished until the exact-head CI is green and merged. The broader next engineering task remains *one unified evidence-first planner*, not more target-specific publication rules.

## v0.18.344 verified CI and next read-only acceptance (2026-11-01)

**Merged code:** [PR #1257](https://github.com/ienam-smarthome/HomeBrainOS/pull/1257) as `b8d27d5d98bd7c1b11036baecef93c13e79c444b`. Exact-head `7543eeb49c69762f6d082356d0b400d3a257a9ec` passed **all eight check runs**, including 5,709 Python tests, release metadata, add-on container smoke, scorecard integrity and validations. First run caught a real contradictory `deviceId` versus `id` metadata flaw permitting source-ID linkage; repaired so *every* explicit config identity must match before a driver-source read is possible. The final exact-head rerun passed. Repository development made no Hubitat/HA changes.

**What is enabled:** Model-first remains **opt-in, disabled by default**. For a verified single-device read-only telemetry investigation only, one target ID-scoped config record may authorize one 8,000-character driver-source read when independently linked driver code ID and live read-only gateway are present. A source read is not the same as verified driver behavior. When mutually inconsistent saved clock sources lack independent corroboration, model prose is not published unmodified; the previous bounded source-typed fallback is used with `modelFirstRejection=unresolved-source-clock-conflict`. This prevents the observed misleading confidence but is not a generic semantic-entailment solution. User must not interpret a host-rendered answer as the model becoming more capable.

**Next acceptance:** Install v0.18.344, use `model_first_investigations_enabled: true` temporarily and submit *once*: "Investigate why Bedroom 3 Mesh reports offline while MQTT reports connected. Explain what the evidence proves, what remains uncertain, and the most useful next read-only check. Do not change anything." Return answer and complete Technical JSON. Check whether `sourceAuthority.linkedDriverSourceChunkRetrieved` became true and whether the `answerPublicationDecision` shows source-typed fallback versus model prose. If no true verified driver metadata exists, no source read should occur. The old planner still has overlapping retries. **Human-evaluated accuracy / Claude gap NOT MEASURED.**

## Live v0.18.343 failure and v0.18.344 source-proof candidate (2026-11-01)

**Actual user-read-only v0.18.343 telemetry result:** 8 Gemma 4 31B Cloud rounds, 8 tool calls, **34,473 ms elapsed**, 29,416 ms provider. The opt-in `sourceAuthority` packet was present, showing `independentBrokerPacketsVerified=false`, `verifiedInstalledDriverBehaviour=false`, `physicalCauseEstablished=false`, and `sourcesAgree=false` (saved `lastSeen` age 502.6h versus `dataAgeSeconds` age 45.1h). The extra verified-target `hub_get_device(mode=configuration)` succeeded, as did app 3950 config and bounded device logs/history, but **no driver source was read**. Gemma still asserted a broker-held live session, total telemetry silence since Oct 12, exact watchdog cause and a physical connection mechanism; these conclusions were not established. This is a **failed factual grounding review**, despite improved fluency and unchanged draft publication. The model's suggested driver ID 3686 is NOT independently established merely by appearing in prose.

**v0.18.344 candidate hypothesis:** Connect read-only source discovery to the existing ID-based metadata guard. Whitelist a single verified source ID from a successful matching device config, record only that identity, and read at most one bounded driver-source chunk when the actual gateway permits it. Keep raw code in request-local provider/tool payload, not API diagnostics. Distinguish actual source chunk retrieved from independently verified method semantics. **General evidence-conflict gate:** a material unresolved contradiction in clock sources without independent corroboration should take the prior source-typed fallback, not publish unconstrained prose because a model included generic uncertainty. This is a provisional safety step, not a full claim-entailment engine or a case-specific phrase blacklist. The full planner still has multiple retries and needs consolidation. No Hubitat/HA mutation; default-off remains the safe production mode.

**Next acceptance:** after all exact-head CI green and merged build installed, execute one single-device read-only same question, inspect driver source link, source read, `modelFirstRejection`, answer publication mode, source-role evidence and root-cause claims. Until human source review, formal answer quality score remains NOT MEASURED.

## vNext v0.18.343 verified merge and next acceptance (2026-11-01)

**Repository:** [PR #1255](https://github.com/ienam-smarthome/HomeBrainOS/pull/1255) merged `b11a66a02a171b1a6dd200b29a46eac8f8b16080`, v0.18.343. Exact PR-head `8df458bc7dd0ff59b28e957bb4540e143226734c` had **all eight GitHub checks green**, including **5,704 passed** Python tests, release metadata, container smoke, scorecard and validation. Initial CI caught missing metrics registry entries and synthetic identity fixture; both corrected, final exact-head rerun green. No live Hubitat or Home Assistant changes.

**New generalized source-authority path:** When the existing opt-in model-first toggle is enabled, single-device telemetry investigations now provide a compact typed source-role record to the actual final model prompt, keeping Hubitat-saved state, sampled logs/events, contradictory ages, model-suggested causes and independent broker/driver/physical proof separate. If a target-scoped log and mixed history were read but no device configuration was attempted, the host may make one additional read-only, live-admitted target-device config read before final synthesis. No other domain or commands changed. Natural-language semantic certification is still **not implemented**. This is source-context and tool-selection development, not another claim-substitution phrase patch.

**Next acceptance gate:** Install v0.18.343; keep `model_first_investigations_enabled: true` **only for this read-only test**. Ask once: "Investigate why Bedroom 3 Mesh reports offline while MQTT reports connected. Explain what the evidence proves, what remains uncertain, and the most useful next read-only check. Do not change anything." Return full answer and Technical JSON, especially `investigation_coverage.sourceAuthority`, `incidentReasoningDepth`, `answerPublicationDecision`, `modelFirstDraftBoundary`, model/tool rounds and elapsed. Check whether model no longer asserts unverified broker/LWT or a precise physical silence duration; source report coverage and answer usefulness must be human reviewed. If it invents an upstream cause again, toggle model-first **off** rather than patching a new word pattern. Official same-evidence benchmark metrics remain NOT MEASURED; do not claim Claude parity.

**Next architectural work:** Consolidate the model-driven read planner and remove overlapping checkpoint retries, then evaluate lighting/heating/ventilation/telemetry with identical source packets; independently verify model-authored facts before promoting provisional free-form publication broadly.

## Live v0.18.342 model-first failure and source-authority milestone (2026-11-01)

**Actual user-run read-only diagnostic, installed v0.18.342:** Ollama Cloud Gemma 4 31B, **8 model rounds, 7 tool calls, 37,663 ms elapsed**, 32,285 ms provider and 3,154 ms aggregate MCP HTTP. `answerPublicationDecision.mode=model-authored-provisional` and `publishedIsFirstModelDraft=true`: new pipeline truly published Gemma's explanation, unlike v0.18.341. Model output was more natural and reconstructs a roughly five-minute deviceHealth stale/unknown loop, but **made unsupported definitive claims**: ghost broker session / broker LWT not received, complete telemetry failure/precise silence duration, and a verified broker disconnect mechanism. Independent broker observation, physical packet, driver method analysis and actual rule decision were not retrieved; `rootCauseVerified=false` and source-clock discrepancy **502.3 h versus 45.1 h** remain in the same packet. The user's Claude answer included additional independent investigations and is NOT a same-packet reference. One unblinded real first-run answer reviewed; formal scored factual accuracy and cross-domain generalization **NOT MEASURED**.

**Next generalizable v0.18.343 candidate:** Canonical source-role/authority envelope for model-facing final synthesis and technical diagnostics, and at most one genuinely ID-scoped, live-advertised, non-mutating device configuration check after targeted state/history/logs, only when opt-in is enabled. It does **not** add scenario-specific phrase bans, certify model prose or independently observe MQTT broker packets. The original read planner still has multiple retries; this is a source-context foundation for a future unified planner, not completion of the redesign. Default-off and previous source publisher remain rollback. Next acceptance obligation is exact-head CI and a single read-only first attempt after new version installed; human review must reject unsupported definitive causes regardless of fluency.

## vNext v0.18.342 merged and user acceptance gate (2026-11-01)

**Verified main:** [PR #1253](https://github.com/ienam-smarthome/HomeBrainOS/pull/1253) merged as `2b09dec6ca6ae4e73db417aae0b0b7cab38afb75`; v0.18.342 is available from the repository. Exact PR head `c2b779c2d27b93f414f87c33f36eb1045a9dd2e8`: **all eight GitHub check runs succeeded**, including full Python suite **5,700 passed**, container smoke, metadata/repository validation, tests and scorecard integrity. Initial CI also caught one test-double compatibility failure for a new optional API argument; corrected by preserving the original two-argument default-off path and rerunning the final exact head. Tests and image-building prove integration, not answer quality.

**Next single read-only test:** User installs v0.18.342, enables `model_first_investigations_enabled: true`, restarts add-on and submits once: "Investigate why Bedroom 3 Mesh reports offline while MQTT reports connected. Explain what the evidence proves, what remains uncertain, and the most useful next read-only check. Do not change anything." Capture full answer, version and Technical JSON (`answerPublicationDecision.mode`, `modelFirstRejection` if any, `modelFirstDraftBoundary`, `incidentReasoningDepth`, elapsed, rounds and tools). A model-authored provisional answer is **not** automatically a true explanation; compare against available source receipts and user-provided Claude reasoning without treating their different source coverage as matched evidence. Default-off rollout/rollback and no home mutations remain mandatory. Human-reviewed quality is **NOT MEASURED**.

**Next architecture milestone:** source-complete read planner and cross-domain model-first contract; retire old overlapping retries only after demonstrable same-packet correctness and safety regressions. Do not continue adding case-specific phrase bans.

## vNext opt-in model-first telemetry pilot (2026-11-01; merged v0.18.342)

**New live baseline:** user submitted an actual **v0.18.341** Gemini-like Ollama Cloud Gemma 4 31B read-only investigation of Bedroom 3 Mesh: **8 model rounds, 7 tool calls, 34,261 ms elapsed**, provider 29,542 ms. The report still published five host-rendered claim-catalog statements. Provenance shows `modelProseAuthorizedForPublication=false`, `publishedIsFirstModelDraft=false`, `modelFirstDraftBoundary.authorAnswerUnchangedAtSharedBoundary=true`. The scoped evidence checked current attributes, 24-hour deviceHealth events, logs, Tasmota label filter and room but did NOT verify driver method behaviour, rule 3950, a sibling comparison, broker endpoint packets or ICMP. Source-class checks were not substantive proof. The published answer was much less useful than the user-supplied independent Claude investigation, which had additional separately obtained sources; **not a matched-source model A/B or a certified physical cause**.

**vNext candidate implementation:** opt-in `model_first_investigations_enabled` (default false) changes ONLY single-device `device_telemetry` final no-tools synthesis from JSON claim-ID selection to a natural model-authored explanation. A strict original-model-draft provenance equality, bounded read-only source scope, reported-status presence and high-risk cause/physical-action claim checks decide whether to publish the *unchanged* model explanation. The existing source-rendered answer remains the fallback. No automatic semantic entailment proof is claimed; a vetted explanation can still make a subtler unsupported inference, requiring human review. No new reads or model rounds added; the old read planner and most retries remain in this first vertical slice. No control, lighting, heating, routing or Hubitat/HA writes are changed. Safe rollback: set option false and restart.

**Status:** candidate awaiting exact-head CI and a user-run, strictly read-only first-attempt quality test. Formal evaluation remains **NOT MEASURED** beyond the observed single v0.18.341 performance. Test a real v0.18.342 model-first reply, source coverage and publication mode; if meaningful quality does not improve, do NOT add another phrase-specific gate. Next architectural step is the single-investigation planner and independently reviewed cross-domain model-first evidence contract.

## Q3 verification and next source-contract milestone (2026-11-01)

**Verified repository main before this branch:** `4d98060bf3006d4fe1719f5a565e7ca316a4864d` merged [PR #1250](https://github.com/ienam-smarthome/HomeBrainOS/pull/1250) as **v0.18.340**. All **six** reported exact-PR-head GitHub check runs succeeded at `00525ba660b6f95087ef43cd7ec3501ac99a1473`: full Python tests, test, smoke, metadata, scorecard integrity and validation. This proves code/CI integration, **not** model answer improvement. No v0.18.340 HomeBrain production trace has been reviewed. The previously captured v0.18.339 baseline remains **11 rounds, 9 tools, 51.152s** on changing live evidence; do not describe it as a matched speed baseline.

**Q3 cross-domain contract foundation merged:** [PR #1251](https://github.com/ienam-smarthome/HomeBrainOS/pull/1251), merge SHA `a5243e6976b50e6c60df9fab3e810074584ae301`, new maintained add-on source version **v0.18.341**, **all seven exact-head CI checks green** at `0698c9f3b6f3f32a4917afee350d1e75e5789423`, **5,694 Python tests passed**, plus smoke, metadata, dedicated scorecard, test and two validations. The first revised CI run caught missing release-index/module-map entries; these were corrected and the final exact-head rerun passed. **Code/test proof is not a measured answer-quality result.**

**Implemented cross-domain foundation:** factor strict JSON claim-plan validation into one domain-neutral, source-catalog-only verifier, retaining the existing telemetry adapter/selection and fail-closed runtime policy. Introduce an **offline-only** time- and target-scoped recorded-command adapter derived from authentic typed Hubitat command event receipts; it separates app-issued command, upstream decision and physical execution. Add negative controls for wrong device, historical time window, ambiguous app issuers, missing command evidence, injected model prose and non-offline telemetry states. Fix the hardcoded assumption that every device's reported health value is `offline`; caveats must match the actual reported state. This is not an enabled lighting/heating publisher, semantic certification or a benchmark score. No change was made to live Hubitat or Home Assistant. Package version advances to v0.18.341 as required by release validation for any maintained runtime module change; no new model/tool calls are added.

**Measured evaluation status after PR #1251:** 0 independently authenticated first-attempt frozen production cases; formal factual grounding, first-answer usefulness, latency gain and Claude parity all **NOT MEASURED**. CI negative controls are engineering safeguards, not quality scores. Next acceptance obligation is a single **read-only** HomeBrain run after installing v0.18.341 (record the exact installed version/build) using an exact question, complete natural answer and technical JSON (including model/tool rounds, wall time, publication decision/rejection and source coverage). Confirm the installed build/version first; do not make live Hubitat or HA changes. Only then decide whether the reduction in retries and model-directed final publication worked. Future lighting/heating adapters require their own scope-matched witnesses and same-packet review before runtime enablement.

## Live v0.18.339 publication and investigation escalation defect (2026-11-01)

The user submitted a genuine read-only v0.18.339 Bedroom 3 Mesh JSON: 9 tool calls, 11 Ollama Cloud rounds, 45,291 ms provider, **51,152 ms elapsed**. It checked 48 hours of target state/history (12 status events, 0 commands), scoped logs, a Tasmota labelFilter, dependents, app 3950 config and device configuration but still returned the deterministic concise status projection. `modelFirstDraftBoundary` captured the first no-tools answer, unchanged at coordinator and author, yet `authorAnswerUnchangedAtSharedBoundary=false`, `answerPublicationDecision.mode=concise` and `publicationBoundaryShadow.replacementPerformed=true`; no model claim plan was admitted. This is **not proof the raw draft was a valid JSON plan**; no raw candidate text was exposed and the old gate omitted reasons when the outer message changed. No driver source, physical telemetry, broker or power evidence proved root cause.

**Confirmed code-level architectural problems:** `shared_investigation_completion` demanded `raw==coordinator==author==incoming` before even attempting to validate a claim plan; host-side confidence calibrations can change `incoming` despite intact original provider provenance. Meanwhile `mcp_agent_orchestrator` maintains separate incident checkpoint, general evidence retry, depth retry and follow-through branches, so partial-cause uncertainty can repeatedly reopen tool selection even after adequate bounded target status/history/log receipts.

**v0.18.340 candidate:** revalidate authentic raw claim plans against final normalized receipts independent of outer host-message equality; retain raw/coordinator/author identity checks; expose only fixed rejection categories. Make source-qualified JSON output unambiguous in the existing synthesis prompt. Add a general single-target telemetry evidence-saturation stop (targeted status/history/logs plus a meaningful checked discriminator or one offered source-gap checkpoint), and a six-round read-tool budget. Non-telemetry, controls, explicit multi-device comparisons, lighting/heating and source-code requests stay outside that contract. No new provider/MCP calls or live home mutations. Model prose remains **not semantically certified**; public text is compiled exclusively from source-attested facts.

**Next acceptance obligation:** run exact-head CI, confirm true live `answerPublicationDecision.mode=model-directed-source-claims` if eligible, and inspect `modelClaimPlanRejection` if not. Measure overall model/tool rounds, timing and substantive quality from a fresh read-only trace. Formal cross-domain quality and Claude parity remain **NOT MEASURED**.

## Live v0.18.338 result and Q3 model-directed claim publication (2026-11-01)

User-supplied read-only v0.18.338 Bedroom 3 Mesh result: **11 model rounds, 10 tool calls, 44,488 ms provider, 74,284 ms dominant whole-hub MCP call, 130,628 ms total**. The model's first final draft was genuinely captured and unchanged at coordinator and author boundary, but `authorAnswerUnchangedAtSharedBoundary=false` and `publishedIsFirstModelDraft=false`; the deterministic telemetry finaliser still replaced it. This is measured evidence, not proof of the model's semantic answer quality. A nested `homebrain_filter_devices(deviceHealth=stale)` scan invoked an expensive unscoped 207-device inventory, escaping v0.18.336's name-filter-specific broad-read block.

**v0.18.339 candidate:** establish a **narrow proof-carrying answer plan**, using source-typed model-selected claim IDs, mandatory uncertainty, strict source/target/clock checks, no arbitrary free-form prose, no changed/unattested model draft, and host-rendered verifiable statements only. The model directs claim choice and order; every published word remains evidence-safe. Other domains, commands and ambiguous histories remain fail-closed. An expanded `single_device_read_scope` also blocks non-target attribute filters that otherwise launch hidden whole-home reads, without restricting explicit comparisons.

**Do not overclaim:** This does NOT yet certify full model-authored natural language or causal conclusions in lighting/heating. It is proof-carrying model-directed selection, not semantic free-form entailment. No same-packet first-attempt speed/quality score, multi-domain clinical assessment or Claude parity is measured. A later generalized proof adapter and independently evaluated semantic-entailment admission strategy are required before permitting unrestricted model prose. No live home-system mutation is authorized.

## Live v0.18.337 model-first publication evidence (2026-11-01)

A full new read-only Bedroom 3 Mesh trace was supplied after installing v0.18.337: **11 Ollama Cloud Gemma 4 31B model rounds, 11 tool calls, 46,924 ms provider and 61,224 ms overall**, versus v0.18.336's 5 rounds, 6 tools and 21,232 ms. These were not controlled identical source windows. v0.18.337 blocked one unverified driver-source ID but later invoked scoped logs (one unusually slow 9,342 ms read), device config, dependent apps, source discovery, a failed app-config lookup, app-list and source workbench with `sourceRetrieved=false`. Its final answer again replaced the incoming synthesis; the API reported `incomingVerifiedRawModelDraft=false`, so raw model behavior could not previously be compared with the fixed publication output. No driver methods, broker source frames, plug power or physical cause were proven. The 11 status reports are hub-side `unknown`/`stale` cycles, not physical reconnections.

**v0.18.338 model-first foundation candidate:** Capture the genuine first no-tools provider text request-locally *before* the synthesis validator, separately retain the coordinator and orchestration outputs, and report only fixed equalities under `modelFirstDraftBoundary` after source-backed completion. This does **not** authorize raw model prose as evidence or publish speculative conclusions; it is the necessary identity/provenance foundation for an eventual typed claim/witness admission gate. No extra model or MCP rounds; no home-system changes. Maintain **NOT MEASURED** for model-first answer accuracy and speed. Next task is source-attested claim admission and cross-domain regression review, not another device-name heuristic.

## Live v0.18.336 comparison and source-identity finding (2026-11-01)

**Observed v0.18.336:** The user provided full device-telemetry response and JSON for Bedroom 3 Mesh. The response is still concise and source-based, but `publicationBoundaryShadow.replacementPerformed=true`, `incomingVerifiedRawModelDraft=false`; the model's full explanation was **not source-attested**. Gemma 4 Ollama Cloud performed **5 model rounds**, **6 tool calls**, **17,553 ms provider time**, **21,232 ms elapsed** (prior v0.18.335 was 5 rounds, 8 calls, 19,018 ms provider, 24,910 ms elapsed). Unrelated 207-device whole-hub scan and generic name filter did not recur; no `single_device_broad_reads_suppressed` counter appeared, so the guard's causal impact cannot be isolated from this trace. Different source windows prevent a controlled speed A/B.

**Specific remaining blocker:** the model sent `hub_get_source(type=driver,id=7103)` which failed. **7103 is a verified device-instance ID, not a verified driver source-code ID**. The source/method semantics, true endpoint last packet, broker state and physical outage remain unproven. The 11 bounded deviceHealth records alternate `unknown` and `stale` approximately every five minutes; this does not prove physical reconnection. The saved `lastSeen` on Oct 12 and static `dataAgeSeconds=162325` disagree (500.2 vs 45.1 hours at read).

**v0.18.337 source-identity candidate:** enforce a general read-only source-code-ID provenance gate on driver-source reads only after a positively established single-device target, preserving matching metadata and other sources, without new model calls. If merged, leave actual live impact **NOT MEASURED** until a comparable test. **Still open:** independently attest the raw model draft and gate model-authored claims by receipts across telemetry/lighting/heating. Do not mistake a blocked incorrect read, a checked source class or current deterministic answer for confirmed root cause or Claude-level reasoning. No home-system writes.

## Live v0.18.335 Q3 observation and next general architecture step (2026-11-01)

The user supplied one full **live, read-only v0.18.335** Bedroom 3 Mesh investigation response and JSON. It used **Ollama Cloud gemma4:31b**, **5 model rounds**, **8 tool calls**, **19,018 ms provider**, **22,894 ms agent**, **24,910 ms elapsed**, and `metrics.outcome=unresolved`. The typed target history returned 11 driver status reports (`deviceHealth` alternating unknown/stale roughly every five minutes), zero recorded commands, `healthStatus=offline` and `mqttStatus=connected`. `lastSeen` dates to 12 October while `dataAgeSeconds` is frozen at 162325 seconds, producing **499.5 versus 45.1 hours** at the recorded read. None establishes physical last contact, plug power or source method behavior. The final answer correctly qualifies the transport/metadata distinction but misses the regular health-status pattern and driver method verification.

**Architectural evidence:** `answerPublicationDecision.mode=concise` worked, but `publicationBoundaryShadow.replacementPerformed=true` and `incomingVerifiedRawModelDraft=false`: current output remains **deterministic source-publication**, not certified model prose. After targeted state/history/log/config reads the model also called a whole-home 207-device context snapshot and a generic `Tasmota` name filter, without any verified contribution to the answer. That unrequested breadth is a legitimate general tool-selection defect. A prior 11-round ~42s trace used other source conditions and is **not** an exact matched A/B or proof of speed gain.

**v0.18.336 candidate:** an evidence-anchored tool admission guard suppresses late whole-home context and unrelated name filters *only* after a single user-named target has matching ID-scoped event history and targeted state; source-specific driver/log/upstream tools and comparisons remain allowed. If full CI passes and merged, record merge SHA and leave actual runtime improvement **NOT MEASURED** until the next live execution. The next major architectural obligation is **authentic raw model draft provenance plus source-attested claim gating** before publishing any free-form model conclusion; don't claim that v0.18.336 solves model-first narration or physical cause. This addresses redundant read breadth, not an MQTT-specific root-cause patch.

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
- **Q1 fixed-packet baseline preflight delivered:** [PR #1234](https://github.com/ienam-smarthome/HomeBrainOS/pull/1234), merged at `360ed4abb96e1f4be934397be499d6f485939ee3`, all **6 exact-head CI checks green** (full Python test suite, add-on smoke test, scorecard integrity, repository metadata and two validation checks). The 18 curated read-only source cases now export as stable SHA-256 model-facing packets **without** private reviewer rubrics. New offline comparison preflight rejects different input hashes, non-first-attempt/duplicate runs, noncanonical build IDs and raw private answers; paired metadata is **not** a human-reviewed score. The 13 legacy live/control tasks remain distinct. No add-on runtime behavior, provider call or device mutation changed; **quality remains NOT MEASURED**.
- **Newest Q1 device-telemetry response reviewed:** [Anonymised source review](ANSWER-QUALITY-Q1-MQTT-RESPONSE-REVIEW.md) of one actual v0.18.331 Free Gemma response: **43.533s**, **13 tool calls**, **10 model rounds**; Hubitat reported conflicting offline/MQTT-connected statuses and inconsistent cached clocks. Recent local health-status events did **not** independently prove live endpoint data, and retrieved driver source was not linked to installed code or method execution. The host finaliser replaced model prose with a lengthy templated history, then appended technical-only details. This is a second cross-domain full trace, but input prompt/deployment SHA are not independently attested, so the formal frozen baseline remains **NOT MEASURED**.
- **v0.18.332 presentation refinement merged:** Generic telemetry responses foreground the diagnosis; code offsets and the complete missing-source-method ledger remain in structured Technical details; no empty command-source heading is emitted. Bounded command-delivery uncertainty and one relevant source-method limitation remain in the answer. CI validated 5,633+ Python tests, the add-on smoke test, repository metadata, offline scorecard, and two additional validation jobs; **seven exact-head checks all passed**. This does not prove a same-evidence improvement in model reasoning, and no extra model/tool calls or live Hubitat/HA writes were introduced.
- **New v0.18.332 real read-only follow-up:** A second privately reviewed device-telemetry trace (same registered question but **new live evidence**) took **55.132s**, 11 model rounds and 13 tool calls, against earlier v0.18.331 **43.533s**, 10 rounds and 13 calls. The new answer was clearer about broker/session versus endpoint data and omitted technical code offsets; it still repeated the same clock discrepancy twice and used a costly 207-device whole-hub context read and an unsuccessful driver/app-source lookup. **Not** a same-packet paired improvement or causal speed regression; **0 authenticated frozen first-attempt grade**. Review is appended to [Q1 MQTT response review](ANSWER-QUALITY-Q1-MQTT-RESPONSE-REVIEW.md). The new release was reported installed as v0.18.332, but deployed source SHA and exact prompt were not independently attested.
- **Q1 structural correction under review:** A source-derived clock assessment was independently rendered by typed history and shared completion. One generic rendering site will use the shared structured clock check when available; the direct standalone renderer retains its source-derived fallback. The full structured record, source uncertainty and read-only boundary remain unchanged. This is not a model quality or runtime speed claim.
- **v0.18.333 single-clock provenance merge:** [PR #1238](https://github.com/ienam-smarthome/HomeBrainOS/pull/1238), merge `f527bec5fda4321edefbb6114ab940f67a6dbe99`, **all 8 exact-head checks green** (full test suite, two test jobs, metadata, add-on smoke, scorecard and two validations). One shared structured clock check now appears once next to targeted device state instead of a duplicate after the answer; direct callers preserve their source-derived fallback. Full structured evidence, source gaps and unresolved verdict remain unchanged. No added MCP/model calls or live device writes. **No tested v0.18.333 answer-quality/latency outcome.** Revert this small rendering handoff if cross-domain evidence coverage regresses.
- **Q1 next generalising bottleneck:** investigate the device-incident checkpoint + depth + progress retry policy and the host's model-prose replacement using fixed source packets, because the latest v0.18.332 trace made a 207-device bulk read, attempted an inapplicable app-source lookup, and spent 49.0s in provider rounds despite an already bounded status explanation. This is an observed inefficiency **candidate**, not evidence that cutting tools alone improves accuracy; do not introduce room-specific wording filters or remove safety evidence. Both telemetry traces are already supplied and source-reviewed privately; do not request them again.
- **New v0.18.333 telemetry full trace reviewed (separate changed live evidence):** The latest user's read-only HomeBrain answer reported **41.885s wall**, **40.327s agent phase**, **36.622s provider**, **7 tool calls and 11 model rounds** on Free Ollama Cloud Gemma. Previous real runs were v0.18.331 **43.533s/10 rounds/13 tools** and v0.18.332 **55.132s/11 rounds/13 tools**; **these are not identical frozen source packets** and do not prove a causal speed or first-answer accuracy improvement. v0.18.333 shows the single clock warning working, but still replaces incoming model-oriented prose with a long typed report and spends 11 provider rounds. The physical outage cause and actual driver method semantics remain unverified. The user's supplied JSON was complete; don't request it again.
- **Q1 model/publisher boundary observability merged:** v0.18.334 PR #1240 (all seven CI green) added privacy-minimal, ungraded `investigation_coverage.publicationBoundaryShadow` metadata when the host replaces an incoming response with source-typed telemetry history: fixed strategy label, coarse word-count buckets, incoming message present, replaced flag, and explicit **no authenticated raw model draft**, **no quality score**. The code does **not** enable unconditional model prose, add any calls or alter the physical-cause boundary. A single neutral fixed evidence packet renderer makes existing curated source packets copyable to Claude and Gemma for future **human-reviewed same-evidence A/B**, without exposing grader rubrics. Latest source reviews remain ungraded, **0 certified frozen first attempts**.
- **Q1 next action after #1240:** Ask Claude the exact synthetic/anonymised no-tools packet `aq_network_broker_vs_device_health` generated by `scripts/answer_quality_comparison_prompt.py`, retain its verbatim first answer and disclosed model/provider privately, and acquire an independent Gemma answer using **exactly the same packet** before blinded review. No benchmark numerator/denominator is certified yet. Inspect runtime shadow metrics only after explicit v0.18.334 installation, and never mistake incoming outcome text for authenticated original model prose. Before making model-led publication default, develop source-attested claim gating and cross-domain negative controls across causal lighting, heating, telemetry and source-integrity gaps. Do not ask for already supplied live MQTT JSON again.
- **Q2 first Claude-attributed offline reference received (unscored):** User supplied one concise Claude-style answer to the fixed `aq_network_broker_vs_device_health` evidence packet; the prompt hash `74ccff7fa2c23852655d12b45f6f5cbb6a3315de8c7647cac7b03441282f7150` was independently verified against unchanged synthetic fixture. A [privacy-safe qualitative source review](ANSWER-QUALITY-Q2-CLAUDE-REFERENCE-REVIEW.md) finds the key broker-vs-endpoint distinction and watchdog interpretation supported, with a minor caution that `healthStatus` is not independently verified physical state. **No Gemma result on this packet; Claude later self-reported Sonnet 5.5 (unverified model identity), while tool settings and actual prompt delivery remain unverified. Zero paired A/B runs, official scorecard NOT MEASURED.** Do not count prior HomeBrain live traces as matched Gemma responses, request the Claude answer again, or claim Claude parity.
- **Q2 source-matched comparative response now captured (unscored):** The user upgraded Termux dependencies after a failed `curl` startup and successfully invoked Free Ollama Cloud `gemma4:31b` directly, temperature 0, no MCP tools, same frozen `aq_network_broker_vs_device_health` question, SHA and three evidence facts previously provided to Claude (whose later response self-reported Sonnet 5.5). Gemma accurately stated broker connection vs endpoint stale telemetry and watchdog-only `lastActivity`; its explanation and read-only diagnostic were shorter/less connected than Claude's. Claude mildly over-trusted reported offline health as physical state. **One qualitative source-matched pair, but prompt whitespace differed and Claude model/settings / original first-run authenticity are not independently verified. No official graded A/B, scorecard NOT MEASURED.** Full source-bounded nonprivate assessment in [Q2 qualitative comparison](ANSWER-QUALITY-Q2-CLAUDE-REFERENCE-REVIEW.md). Do not ask for either answer again.
- **Q3 production publication architecture candidate v0.18.335:** the final shared telemetry layer no longer must print a full detailed device audit for every ordinary question. A general source-typed publication-policy module selects a **concise source-backed explanation** by default and retains the previous full renderer for **explicit detailed report** requests or **evidence-rich truncated/command/watchdog-correlation histories**, so source-critical facts are not hidden. Full normalized history, clock inconsistency, source limitations, metrics and physical-cause unresolved status remain structured. This reduces *published verbosity* without additional model/MCP calls; it **does not yet certify or preserve arbitrary model-authored prose**, because prior synthesis validation is not full source attestation and might publish a fabricated physical cause. No verified live latency, first-answer quality or Claude-parity gain; official scorecard NOT MEASURED. Compare actual before/after output on fixed cross-domain receipts and then design independently attested model-claim admission rather than disabling safeguards.
- **Current active task: Q1 same-packet evaluation and publication simplification.** Both complete cross-domain traces are source-reviewed privately. **0 independently authenticated frozen first-attempt reviews**, **two source-bounded domain reviews plus a second MQTT-version follow-up**. Follow unchanged 18 synthetic packet fingerprints/13 legacy rubrics; verify new live first-attempt prompt and running SHA, and compare human-reviewed model answers before proposing further publication changes. Do not use a new historical interval as a paired result. Verify exact user prompt/deployed SHA from an existing retained receipt where possible, then build the first eligible fixed evaluation on the unchanged evidence contract; do not retcon this run into a scored sample or ask the user for the same JSON. No user device action needed.

## Milestone tracker

| Milestone | State | Evidence required to close |
| --- | --- | --- |
| Q0: durable charter + fixed inventory + scorecard | **DONE** · PR #1224 · `06592de2a30aaa0e10e84209fbe9c006a242e45a` | CI green; 31 cases defined, 0 quality reviews, empty scorecard says not_measured |
| Q1: reproducible 13 legacy + curated new cases | **IN PROGRESS — two source-reviewed cross-domain traces; no authenticated frozen A/B** | v0.18.330 lighting and v0.18.331 telemetry diagnostics reviewed, v0.18.332 presentation verified in CI; actual submitted prompt/deployed SHA not authenticated, so 0 certified frozen-case scores |
| Q2: source-complete reasoning improvements | **Not started** | Before/after changes pass target cases and cross-domain negative controls |
| Q3: same-evidence Gemma vs alternative model A/B | **Qualitative source-matched pair collected; formal A/B NOT MEASURED** | Exact same transmitted input and model settings/provenance, complete first-attempt receipts and blinded human source review |
| Q4: simplification and acceptance | **First bounded source-publication redesign under Q3 CI; not accepted as final Claude-grade architecture** | Validate same-packet first answers, source-attested model prose, no new cloud rounds, no safety regression |

## Immediate next tasks for future chats

1. Verify current GitHub `main` and Q0 merge SHA, then **continue Q1 baseline**, not another stage patch. This programme's targets are fixed in the charter.
2. Run the scorecard without reviews. Expect `not_measured`, not a success percentage. Use the Q1 fixed-packet export and paired metadata preflight to freeze the **same synthetic source packet** across models/builds; neither export nor metadata pairing is an answer-quality result. Follow [the private Q1 capture workflow](ANSWER-QUALITY-EVALUATION.md) and [historical diagnostic findings](ANSWER-QUALITY-Q1-RETROSPECTIVE.md); never equate old differently-prompted incidents with frozen before/after measurements.
3. **Do not ask for the same JSON again.** The matching Livingroom answer plus full technical JSON are in the private conversation and have been reviewed. The actual input prompt and deployed source SHA were not included in the response, so exact-run status remains **unverified**. Preserve the anonymised assessment; do not count it as a formal first-attempt score or upload raw household evidence.
4. **Registered frozen prompt:** `Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.` Keep unchanged. The reviewed lighting trace was v0.18.330; the 0.18.331 and 0.18.332 telemetry traces used a different live question and different source windows. **Do not** mix them as a same-packet A/B. A future graded frozen run must independently authenticate its literal prompt, model/settings and deployed SHA.
5. Establish the **first eligible** baseline by replaying identical hash-pinned source packets and source-grading real first-attempt answers; then compare separate model-versus-finaliser text, factual grounding, causal calibration, observed wall time and tools. Existing scorecard remains `not_measured` pending eligible human reviews.
6. **First source-matched Claude/Gemma comparison now exists:** the user has already supplied both Claude Sonnet 5.5 (self-reported) and Ollama Cloud Gemma 4 31B answers to the registered frozen MQTT packet; don't request either again. The three evidence facts and question match, but the prompt had small formatting differences, Claude sampling and model provenance are unauthenticated, and no matched wall times are known. Treat as qualitative model reasoning and guard-design input, **not formal first-attempt A/B scoring**. Prior source-private v0.18.331–.333 technical JSONs are already reviewed and must not be recycled as a matched Gemma test. Compare privately against the same unchanged fixture and evidence rubric; no fabricated timings or quality score from lexical matching. This is one cross-model packet pending review. Previous v0.18.331–.333 technical JSONs are already available; do not ask for them again. Continue generic publication and tool-loop analysis with cross-domain negative controls.
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
