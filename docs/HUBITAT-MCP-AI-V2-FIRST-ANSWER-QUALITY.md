# HomeBrainOS v2 — first-answer quality measurement (original development)

**Established:** 8 November 2026. **Baseline runtime:** 2.0.0-alpha.16; **candidate:** 2.0.0-alpha.17 (source annotation only; not yet live verified).
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
4. The report describes browser/server latency, model rounds, native successful/failed attempts, locally rejected arguments, schema-only reads, prior context, distinct *requested* target/attribute counts and event rows from **successful native source receipts only**. Failed, rejected and metadata-only responses do not count as history even if they contain event-scope-looking text. A summed row count is **not** a unique-event count across overlapping receipts. The public-safe report emits only a model fingerprint and aggregate tool/argument-field counts, not arbitrary external model names, tool names or argument keys. Audit schema v2 preserves **not_measured** quality fields. **It does not grade correctness** or claim that requested targets actually returned complete observations.
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

## Next test and release gate

After the two independent alpha.16 source reviews, the next step is a **fresh V2-R3 first answer on installed alpha.17**, using a test MCP connection with effective Read allowed / Write denied verified via configuration (not by sending a write). Share the complete answer and private Technical JSON. Compare only matching returned source scope, historical gaps, model confidence, tool attempts, and latency; changing live events must be recorded as a confounder. Then use a separate frozen domain for transfer.

Alpha.17 changes only the generic model-visible event-scope annotation and release metadata. It adds **no model prompt, extra model round, router, provider, device rule, recorder, V1 or MCP permission change**. Its model-quality effect must be measured live rather than assumed from code tests.
