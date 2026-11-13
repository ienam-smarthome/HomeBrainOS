# HomeBrainOS v2 — Resume original evidence-first development after alpha.75

**Decision date:** 13 November 2026  
**Verified source baseline:** GitHub main after merged PR #1628, V2 `2.0.0-alpha.75`.  
**Status:** The device-control detour has reached limited source-real acceptance. **Return to original model-led cross-domain first-answer reasoning and V1/V2 Gate B.** No runtime/model/driver changes in this milestone; no new permission or delayed-unblock promise.

## Original goal (unchanged)

HomeBrainOS v2 is a deliberately small, privacy-conscious, **model-led native Hubitat MCP assistant** for natural current-state questions, source-real historical investigations, root-cause discrimination, comparisons, normal device control and voice/UI. It should use the live tool catalog, actual original receipts, existing Hub & Device Monitor history where relevant, and external Hub Diagnostics, **without** a fixed question-to-tool lookup, room/incident-specific patches, automatic causal answer rewriting, a replacement V1 planner or a competing HomeBrain scheduler.

**Model owns reasoning, source choice and interpretation.** Host owns live contract validation, privacy boundaries, read/write permissions, required native confirmation, documented source scope and bounded protective controls. Distinguish a device-reported event from a command initiator, a tool response from a physical effect, and absence of records from verified absence.

Supporting standing documents:
- [V1/V2 capability-gaps and Gate A–D](HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md)
- [First-answer quality charter](HUBITAT-MCP-AI-V2-FIRST-ANSWER-QUALITY.md)
- [Source-real live review protocol](HUBITAT-MCP-AI-V2-LIVE-REVIEW-WORKFLOW.md)
- [Causal reasoning acceptance](HOMEBRAINOS-V2-CAUSAL-REASONING-ACCEPTANCE.md)
- [Read-only V1/V2 pairs](HOMEBRAIN-V1-V2-PAIRED-ACCEPTANCE-20261111.md)
- [Holdout result, no causal uplift proven](HUBITAT-MCP-AI-V2-REASONING-HOLDOUT.md)

## PR review — where the development went

| PRs | Outcome / current status |
|---|---|
| #1590–1603 | Restored general causal/evidence-source discrimination, historical freshness and native/monitor evidence, everyday UI and V1/V2 evaluation scaffolding. These are core to the original model-led aim. |
| #1605–1617 | Optional source/claim review, frozen replay and live catalog recovery. Mechanisms and synthetic CI are not proof of model quality; preserve live first-answer tests. |
| #1618 (alpha.65) | Model-led post-write action/outcome review, preserving one native command selection and separating scheduled vs later effects. |
| #1619–1624 (alpha.66–71) | Experimental action/discovery/continuation extensions; **superseded by the explicit rollback PR #1625**. Their historical documents do not describe features currently installed. |
| #1625 (alpha.72) | Restored alpha.65 functional native command/action outcome behavior without deleting Git history. |
| #1626–1628 (alpha.73–75) | Bounded unfiltered inventory recovery, plan-only action follow-through and a general safeguard against manufacturing an event-driven rule for a one-off delay. Keep these only as limited source/safety mechanisms, **not** as an invitation to expand keyword routes or mandatory device workflows. |

**Current alpha.75 source-real acceptance (private first-answer receipts and a separate screenshot, not independently executed here):**
- A naturally worded one-off delayed device effect caused the model to discover the native actuator, inspect advertised commands, **submit the existing native timed command** and receive a source-reported pending deadline. Separate later native device logs show its deadline fired and the device reported the resulting state. This supports the actual **driver-reported timed transition**, not an independent router/endpoint connectivity test.
- A subsequent direct **immediate reverse action** used the native controller command once, received `success:true` and a same-command returned attribute showing the desired state at the command timestamp. This verifies the device-reported requested state; the receipt did not contain an independent router test.
- **Subtle remaining answer defect:** its final explanation treated a timer attribute last updated at an *earlier* deadline as if it were newly cleared by the later immediate command. Receipt freshness is per attribute. This is one observed claim-quality issue, not evidence of a repeated cross-domain pattern or reason to change the successful write path.
- Both successful requests contained only the current-request native command tool receipt(s); previous conversation evidence and app-hub logs must not be silently merged into the same first-answer source window.
- The unintended event-triggered Visual Rule created during the alpha.74 test was **not** touched by repo changes. Its current enabled/paused/deleted state has not been rechecked; never promise that deploying alpha.75 removes it.

**Important distinction:** Immediate blocking/unblocking and the verified native delayed **block** are separate from delayed **unblock**. The driver has not yet provided an independently verified command to *start* allowing access in the future; `allowForMinutes` allows access **immediately for** a duration. Do not make this missing feature the next v2 development milestone or silently add driver/rule/scheduler machinery. Revisit only as a separately scoped feature after native contract and permissions are verified.

## NEXT — Gate B: fresh first answers, more than command success

Prioritise source-real, read-only, **uncoached** first answers from **at least 12 NEW questions across at least six distinct domains**. Use the existing simple Ask/Chat + downloaded PRIVATE Technical JSON. The existing paired V1/V2 kit and optional frozen replay are helpful for matched questions, but not mandatory for routine daily use. Do not recycle the repeatedly exposed internet-control incidents into independent holdout accuracy denominators.

Suggested domain families (choose genuinely new user questions, not code fixture IDs):
1. **Lighting/automation attribution:** focal state report vs actual command issuer vs a listening app, exact timestamps, competing controller paths.
2. **Heating/TRVs:** simultaneous source chronology, actual demand vs setpoint/config snapshot, alternative coordinator mechanisms.
3. **Humidity/ventilation:** trigger threshold, hold/delay start, later fan state, missing interval evidence.
4. **Energy and appliance telemetry:** reported power vs stale/missing volts/current; historical numeric archive vs short native event retention.
5. **Multi-device/time-series comparisons:** common UTC intervals, requested metric, reporting gaps and updated-at chronology across channels.
6. **Hub/system health and Rule Machine diagnosis:** event histories, app/parent contracts, native logs and missing source coverage; no writes.

Include positive controls with *genuinely discriminating* evidence as well as ambiguous/negative evidence. Vary cases so both confident supported explanations and appropriately limited uncertainty are rewarded. Use no-change wording for investigation-only prompts. Hold models/providers, scope and permissions comparable where practical.

### Private evaluation requirements

For each **first** answer, preserve outside GitHub:
- Exact user question and captured answer, connected-model name, runtime version, capture time, elapsed time, original native and optional monitor receipts, any prior-receipt count, read-only permission constraints.
- A 0/1/2 human review of **factual grounding, source completeness, causal calibration, usefulness**; n/a only for truly non-causal questions.
- Focal event vs exact source timestamps/timezone, query `since`/`until`, pagination/limits, sample freshness/gaps, original `isError`/domain errors, reporter vs initiator, missing discriminating sources and competing hypotheses.
- Per-attribute timestamps inside a successful native response; a fresh internet/access or switch field is **not** proof that every other field in the same response was just changed.
- No unsupported definite causes, no false negative claims based on empty bounded results, no unapproved actions, and no assertion that a command receipt alone proves physical device behavior.
- Distinguish a successful **source-reported** later transition from independent real-world enforcement. Record exactly which sources verified each stage.

**Proposed exit criteria from the original standing roadmap (not measured yet):** At least 12 new real first answers over six domains; target ≥90% supported reviewed factual claims, ≥80% useful first answers, zero unsupported **definite** causes (with a nonzero reviewed denominator), zero unauthorized device writes and materially correct source windows. Report scores per case, failures by type and latency rather than converting synthetic CI passes or two successful action examples into a general accuracy claim.

### Engineering decision rule

Freeze the alpha.75 device-action behavior while these new investigations are reviewed. Cluster errors by (1) wrong source/target, (2) insufficient time-window/page coverage, (3) missing crucial discriminating source, (4) native tool/schema error, (5) reporter/initiator confusion, (6) stale field treated as fresh, (7) unsupported causal certainty, and (8) user-facing omission/latency. Select **one transferable evidence-contract or model-sufficiency improvement** only after repetition across independent domains, with fictional regressions and a new prospective source-real acceptance case. Do not add a controller-specific route, hardcoded device ID, second scheduler, synthetic answer patch or automatic final-text rewrite.

## Explicit boundaries

- **V1** stable add-on, existing native Hubitat MCP permissions and user confirmation, independent **Hub & Device Monitor**, and external Hub Diagnostics remain unchanged.
- PR documentation, CI and installed v2 actions are **not** independent verification of the user's actual hub or model's whole-population reasoning.
- Never publish private Technical JSON, source times tied to household routines, device IP/MAC/IDs, credentials or personal records in GitHub.
- There is **no requirement for a production code release** merely to write or execute this Gate B acceptance plan. Next production change must be evidence-led.

## Immediate next activity

Run one **new read-only causal-investigation question** (different from internet blocking) in the installed alpha.75 Ask UI, with "Do not change anything", and assess its FIRST answer against original successful MCP tool receipts. Use the current study protocol rather than coaching it to use a specific source/tool. Continue with additional distinct domains to establish a transfer baseline before changing runtime.
