# Hubitat MCP AI v0.18.359 — explicit rolling-window source grounding

## Grounded first-shot defect
On 2 November 2026 the user asked v0.18.358 for Hallway FP300 motion/presence **in the last 30 minutes**. The first answer (17.468s, five Ollama Cloud Gemma rounds, seven tool calls, Unresolved badge) reported four activity periods / about four minutes **in that window**. Its own read-only device-history receipt (`homebrain_device_history`, label Hallway FP300 sensor, `attribute=motion`) was instead scoped to **one hour**. All eight observed motion transitions and the four paired intervals (252 seconds) were **11:18:32–11:33:47 UTC**, outside the requested **approximately 11:46:24–12:16:24** 30-minute window. No motion events were returned inside the actual requested period. Source-integrity was flagged unverified, so this is not proof the physical hallway was empty or the source captured all physical motion. The answer also overclaimed that event type `physical` and bridge `producedBy` established hardware initiation and that lacking command rows in this device history proved no automation commands existed.

A separately supplied later Claude answer correctly focused on no motion reports in the last 30 minutes and labeled the latest `inactive` as an older report. Claude's additional Matter reachability and driver-configuration claims came from separate reads, not a paired same-source audit.

## General source-first fix
`requested_event_window_evidence.py` reads the ORIGINAL user's explicit bounded rolling interval (last/past/previous N minutes/hours/days), anchors it to the saved read receipt's source-collection timestamp and filters the model's **already obtained** typed device-event rows to that narrower interval. It supplies the model a compact separate source packet:
- Exactly how many source state reports fell inside the requested window, and which were **earlier context**.
- Latest prior state report and its source timestamp (not current independent connectivity).
- Whether the returned evidence has unverified event-stream integrity or is truncated; 0 returned reports is **not proof of no physical detections**.
- Bridge `producedBy` and Hubitat `physical` event tag do not independently prove upstream hardware initiation; `triggered[]` is an event-listener list, not the command issuer.
- A history tool's broader `hoursBack` does NOT redefine the user's narrower window or make the pre-window `temporalAnalysis` aggregate apply to the user's question.

This source note is injected into the **existing single final Gemma synthesis call**. It does not run new Hubitat/MCP tools, issue controls, change installed devices, force new model rounds or replace the natural final narrative with deterministic text. The packet rejects failed or mutating receipts, conflicting source labels, non-typed/unverifiable timestamps and arbitrary/untrusted source values.

## Deterministic offline before/after and limitations
New frozen synthetic sensor timeline keeps the original defect's hour-vs-30-min discrepancy: four historical active/inactive pairs totaling 252 seconds, all older than the requested 30-minute cutoff. The new source packet must report **0 returned in-window motion events**, **8 earlier transitions**, an earlier last inactive state, no original cause/physical execution conclusion. Additional tests cover in-window reports, duplicate rows, hour resolution, missing/failed/foreign target histories, malformed values and final model call placement.

**What is proven:** deterministic source-window packet scoped correctly on synthetic same-timing receipts. **NOT MEASURED:** actual v0.18.359 first-answer correctness, Gemini/Gemma adherence, status outcome, runtime/latency p50 and p95, first-shot source grounding rate, cross-domain behavioral impact. The prior live v0.18.358 Hallway test (17.468s, five rounds/seven calls) remains a **failed** first-answer baseline. Next test should be a **fresh, unrelated read-only source-window question**, not a replay of the same household motion scenario; compare first answer with complete Technical JSON.

## Safety and rollback
Do not assert a physical sensor detection merely because a driver event says `physical`; preserve event reporters vs initiators and source truncation limits. Revert this PR if model output, source isolation, token latency or same-window attribution regresses. **No live Hubitat/Home Assistant reads, writes, automations or settings changed by development.** Merge only on fully green exact-head CI.
