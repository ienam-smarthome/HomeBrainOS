# HomeBrainOS v0.18.318 — Stage 8.3 local historical shadow

## Live prerequisite verified
On 1 November 2026, Stage 8.2 read Hubitat device 7103 from a **verified detailed inventory**. The current Hubitat reports were `healthStatus=offline`, `mqttStatus=connected`, `switch=off`, `power=8`. This verifies the freshness and identity coverage of a Hubitat **reported-state** read only. The 8 W value may be stale, and no physical action, actual online state or cause was independently established.

## First read-only historical evidence view
A new opt-in **Historical Shadow · Local Journal** panel queries the *existing on-box Historical Journal*, bounded to the past 30 days for a **single numeric device ID** with a 50-event cap and no offset. The app reads only locally stored observations already collected. It does not poll Hubitat, backfill events, contact Ollama or mutate journal capture settings. One fresh per-run consent checkbox authorises the query.

The projection permits only allowlisted switch/motion/presence/level/power values and timestamps. It distinguishes independently recorded **collector reception** from an **unverified device-source timestamp**. Sensitive device names, source descriptions, app messages, arbitrary status fields, IP/MAC addresses, secrets and other device records are never included. Gaps are shown as bounded timestamps without raw reasons.

Zero events **never** mean the device had no events; the archive may not cover the period, a collection gap may exist or retention may have removed rows. A returned source timestamp does not authenticate the source clock. `history_complete`, `physical_execution_verified`, `causal_attribution_verified` and `publisher_approval` are always false.

## Safety and scope
- Dedicated POST endpoint requires same-origin, explicit consent, JSON-only input, numeric device ID, running journal, and source-bounded 30-day / 50-row query.
- No Cloud calls, device commands, Hubitat MCP reads, file uploads or normal orchestrator/publisher changes.
- Read-only, privacy-preserving output; no persistent new capture.
- CI uses a mocked Historical Journal and verifies consent rejection, exact device scoping, source/receipt time separation, error handling, bounded projection, absence limitations and no live device/model calls.

## Phone acceptance
Update v0.18.318, open Live Shadow, enter device 7103, tick the **separate Local Journal consent**, and choose **Inspect archived device events (30 days)**. Share the timeline and gap status. A zero-event result is an evidence-coverage finding, not proof of inactivity. Stage 8.3 does not yet use AI for real historical investigation.

Rollback by reverting this PR to v0.18.317.