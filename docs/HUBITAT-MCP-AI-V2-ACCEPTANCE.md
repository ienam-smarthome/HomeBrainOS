# Hubitat MCP AI v2 — frozen first-answer and follow-up acceptance

Date: 2026-11-08
Baseline: v2 alpha.7; candidate: alpha.8.
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
