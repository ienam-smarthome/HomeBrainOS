# Hubitat MCP AI v2 — frozen first-answer and follow-up acceptance

Date: 2026-11-08
Historical baseline: v2 alpha.7 / alpha.8; current candidate: alpha.11.
Mode: **read-only client token** for investigation. Do not perform live device or Rule Machine changes as part of this benchmark.

## Goal and evidence boundaries

Test the clean model-led MCP architecture on previously unseen questions, plus a follow-up depending on the first answer's retrieved source evidence. No model/provider switching or case-specific prompt modification between cases. Record one full, **unedited first attempt** for each question. Green CI verifies software contracts, not actual model reasoning.

Use one frozen input, same target observation window and read permissions for v2 versus v1/Claude/Thaura. Different providers may have different capabilities. Do not compare when source access or capture coverage differs. Do not infer an incident's actor from a Hue/Matter state reporter, a downstream listener, or absence in a bounded log.

## Read-only cases

| Case | First question | Dependent follow-up (same page, no re-prompting of earlier facts) | Check |
| --- | --- | --- | --- |
| L1 | Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything. | Which evidence specifically supports the proposed initiator, and what remains unknown? | Distinguish OFF state, command, app listener, actual actor; source times |
| H1 | When was Bathroom Meter humidity last above 70%, and how long until it fell below 60%? Do not change anything. | Which source events define the start and end, and are there data gaps? | Event times/units, complete or incomplete interval, no invented duration |
| T1 | Why was the thermostat heating when the TRVs did not appear to need heat? Do not change anything. | Which TRV or scheduler readings were actually observed during that interval? | Actual source timestamps, demand versus setpoint, correct scope |
| M1 | What caused the most recent Hubitat low-memory reboot? Do not change anything. | Which records support a memory-triggered reboot versus a scheduled restart? | Separate systemStart, memory warning, reachability gap, causality |

## Procedure

1. Record installed app version, release commit, model/provider, source/server version, hub time zone and MCP token permission scope (never export the token).
2. In the v2 UI select **New conversation**, submit the frozen first question exactly once, and export the **entire technical JSON**. Preserve failures, timeouts, gateway schema-only responses, and partial coverage. Record browser and server latency.
3. Without resetting the page, submit the dependent follow-up. Export the second technical JSON and check `prior_receipts_used` (count of **historical excerpts supplied**, not proof of use).
4. Review factual support for every key number, actor, timestamp and claim. Check that the model recovers prior evidence without inventing a new observation; verify that it makes a fresh MCP read where the follow-up needs current status or additional coverage. Observe whether incorrect/obsolete IDs persist.
5. Start **New conversation**, repeat the follow-up without its prior first question and verify no previous source receipts are reused. Verify expiry/restart behavior separately where feasible. Compare with a second browser session and verify isolation.
6. Capture the same frozen inputs on comparator agents with matching source permissions and windows. Label noncomparable runs instead of forcing a ranking.

## Evaluation columns per sample

Record: case; model/provider; v2 release SHA; MCP server version; source window; first attempt; successful/failed MCP reads; schema-only calls; prior excerpts provided; verified answer facts; unsupported assertions; unverified causes; source gaps; browser/server latency; accepted/rejected/timeout; technical JSON filename + SHA-256.

All numerical success-rate metrics remain **not measured** until genuine denominators and adjudicated source evidence exist. Distinguish confirmed, partially supported, unsupported, and cannot evaluate. Be especially careful that a tool-returned catalog is not counted as executed history.

## Frozen G06 replay limitation

The G06 captures, private provider access and recorded source responses discussed with Codex were retained outside this public repository. Never recreate fake household history as if it were the private capture. Unit tests using fake responses prove the follow-up transport and memory lifecycle only. A real first-answer result requires actual captured fixtures and/or an authorised live read-only run. A timeout before the first model response must remain a timeout, not a pass.

## Safety

Use the upstream **read-only client token** during benchmark runs. The general-purpose v2 can perform writes allowed by another token; this milestone does not change that architecture. The UI confirmation flow is not a substitute for permissions. No hub configuration, devices, rules, credentials, recorder settings or live logs are modified by these tests.

## Status at authoring

Candidate code and synthetic tests: under PR/CI review. Installed alpha.8 acceptance: **not performed**. Live comparison and any claim of better reasoning: **unverified**.

## Alpha.9 evidence handoff checks

The three installed alpha.8 heating exports demonstrated model context loss across follow-ups. Keep the originals outside the public repository. For the next alpha.9 test, begin a fresh page conversation after update and export both the first and dependent question without changing the model or MCP permissions.

Check the first response's original event records independently for returned dates, pagination limits, and source scope. On the follow-up, inspect the following **separate** fields: `prior_sources_indexed` (prior indexed receipt count), `prior_receipts_used` (selected short previews), and `prior_evidence_reads` (model-selected local archive reads). The model may call `homebrain_read_prior_evidence` for additional chunks; such calls are **not fresh Hubitat reads**. Review whether older source timestamps and events are correctly identified, whether bounded history gaps are acknowledged, and whether a fresh MCP query is requested for data the archive never covered.

Passing criteria for source handoff: all retained source reads are discoverable by an index entry, none is silently omitted, and exact relevant redacted source chunks are obtainable when still archived. Passing criteria for model quality remain independent: no fabricated absence claims, correct time alignment and explicit unverified coverage. A fast answer with no tool reads is not automatically better. Record failures without adding domain-specific prompt rules.

## Alpha.10 independent cause-vs-hypothesis gate

Read-only token, fresh conversation, unchanged model/provider, and first answer uncoached. Use a new non-heating incident (such as device offline, humidity/fan or hub restart) to test transfer to a different question type, alongside the unchanged lighting and heating cases. Preserve the initial JSON even if the answer is unsupported. Check:
- The source record's `client_event_source_scope` appears **only** when actual structured event rows were returned, and the original MCP `content` is preserved.
- A returned event minimum is not relabelled a native data-retention boundary; a lookback request is not represented as proof of complete history.
- The answer distinguishes **observation**, **possible explanation**, and **cause supported by discriminating evidence**; unsupported claims of certainty or relative likelihood count as failures.
- If a permitted independent read can separate alternatives, check whether the model discovers and executes it before claiming a verified cause. If such evidence is unavailable, a precise unverified conclusion is acceptable.
- Re-check earlier receipts by source ID where useful; mark missing or truncated data explicitly. Do not alter native hub settings or enable new sources as part of the test.

The alpha.10 source-scope metadata and generic prompt are a **software change**, not evidence of model success. No hidden deterministic veto, claim filter or mandatory model round is added. The real Home Assistant installed trial, with entire exported technical JSON, is the deciding acceptance criterion. A native Events-page versus MCP comparison requires separate authorised evidence; no result is claimed here.

## Alpha.11 first-call gateway accuracy — frozen comparison

**No live mutation.** Use the same read-only MCP client token, Gemma model, connected Hubitat server and unmodified questions. Start each test in New conversation; use only the first exported answer for first-call metrics.

| Case | Exact first question | First-call success standard |
| --- | --- | --- |
| G1 | Investigate the most recent Hubitat reboot. Determine whether it was caused by critically low memory, a firmware update, or another cause. Check available system events and diagnostics. Distinguish verified evidence from possible explanations. Do not change anything. | First `hub_read_*` gateway tool call uses the live top-level `tool` selector and leaf-only `args`; no duplicate `args.tool`; correctly identifies source context |
| G2 | Retrieve the most recent five events for Hallway Light 1, including timestamps and event provenance. Distinguish the reporting device from any proven initiating command. Do not change anything. | Same gateway shape; preserve real events and uncertainty |

For each JSON record installed UI/backend version, model/provider, MCP server version, first requested gateway/leaf, raw parameters, success/error and execution flag, eventual successful native calls, model rounds, server latency and factual support. **Zero malformed first calls is the target, not guaranteed by schema rendering.** Distinguish a locally rejected `contract_error` (`operation_executed: false`) from native `isError` calls. Check the UI still supports direct/flat MCP tools, gateway `{}` schema discovery, and writes/confirmation unchanged in permission simulations only.

Synthetic CI accepts a model stub to verify first-call tool affordances, but only an installed uncoached model run can establish actual first-call improvement. Do not train case-specific argument rewrites or mask rejected calls.

## Alpha.12 selected-leaf schema and latency comparison

Run uncoached G1 (latest reboot, see alpha.11 cases) with same Gemma model and upstream read-only client permissions. In a separate new conversation run G2 (Hallway Light 1 events). Record all MCP requests including `leaf_schema_discoveries`: those are **metadata-only** gateway `{}` catalog calls, not domain query or write executions, so raw count of model `tool_calls` underreports server requests. Confirm the original live leaf enum/type/description reaches the model on a later round after discovery. A mode-dependent restriction present only in prose remains advisory; do not mark the client as rejecting such a combination locally.

Compare first unsuccessful attempt, native `isError`, local `contract_error`, relevant successful reads, unrelated broad log reads, model rounds, total server/browser latency, source completeness, and explicit causal uncertainty. Record whether a repeated question reuses cached leaf metadata. A model stub correcting a malformed typed request is **not evidence** of real Gemma first-call compliance. Model-choice correctness and response speed remain independent acceptance criteria. Do not modify devices, rules, server token permissions, firmware or external recorder during these tests.

## Native flat MCP comparison — architecture gate (no version bump)

Before adding a tool router or changing v2 prompt behavior again, use the upstream server's **existing** `Consolidate tools behind category gateways` toggle to compare real native flat leaves versus gateway envelopes. A hub-wide settings change can disrupt other MCP clients even though masters and overrides are unchanged; obtain user approval for the specific test and reset the toggle afterward. Read-only token, no device operations or firmware changes.

The exact G1/G2 questions, uncoached first-answer protocol, repeatability, metrics, cache-refresh/other-client risks, rollback and go/no-go criterion are in `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md`. Test-only stubs verify v2 *compatibility*, not any live model improvement. Expect zero `leaf_schema_discoveries` in direct flat mode (full leaf schema is in `tools/list`), but do not infer lower latency: the advertised tool catalog is larger and may exceed provider/context budgets. Preserve failed prompts and outputs in the comparison.

## Flat-mode real Gemma outcomes and next source-alignment tests

Three real alpha.12 flat-mode outputs were received on 8 Nov 2026 and reviewed as **read-only behavior**, not proof of read-only token restrictions. G1 (reboot) 1/1 calls, 5.792s, 2 rounds; G2 (five recent events) 2/2 calls, 8.815s, 3 rounds, **1 prior receipt used**; G3 (OFF causal investigation) 5/6 calls, 11.962s, 7 rounds, one locally rejected wrong-type app ID. All had **zero gateway-format errors** and **zero leaf-schema catalog discoveries**. G3 supports a 15-second inactive-off mechanism through event times, app settings and both sensor histories, but lacks direct timer callback execution evidence.

The recorded matching alpha.12 gateway G1 had 8 attempted calls with 4 rejections, 4 rounds and 13.779s. Flat G1 was faster but one paired run is insufficient for an architecture decision. There are no gateway-matched G2/G3 results in the supplied comparison. Do not silently upgrade hypothesis to verified cause; lack of unrelated reported commands does not exclude all alternative mechanisms.

The next two **uncoached** flat-mode cross-domain trials are F1 humidity threshold duration and F2 historically simultaneous multi-TRV demand (exact frozen prompts, metrics and rollback in `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md`). Require a **verified effective read-only MCP client policy** before continuing, and do not modify Hubitat simply to validate a model response. Capture failures, missing event windows, timeline errors, unsupported snapshots/precision, model rounds and wall time. Do not introduce case-specific patch logic or new tool router based only on three samples.
