# HomeBrainOS v0.18.60 — Rule proposal evidence contract and native feasibility calibration

## Live retest
On 2026-10-22 the v0.18.59 live Claude-comparison benchmark correctly returned `live-read` with 7 read-only tool calls and 2 free Gemma rounds in ~19.3 seconds. It identified the reported sensor mismatch (ID 7764 is the FP300 Toilet sensor), app 4019, and the competing ~30-second inactive OFF versus requested 10-minute night timer. However, receipts merely exposed device/config **field names**, not source values. Full action list, delay settings and lockout side effects cannot be independently certified from these receipts.

The response overstated the combined native authoring capability: it asserted `hub_set_rule` supported all required Wait-for-Event/timeout/Required-Expression/IF parts, asserted cross-midnight safety, and inferred OFF-only cannot interact with the lockout. A wait with a timeout can continue on either the motion-active event or timer expiry, so additional branching and a final 23:00–06:00 guard are essential. It also omitted an explicit 23:00 trigger for a light left ON before the night window.

At the API boundary `investigation_coverage` was incorrectly classified as **manual_motion_lockout** and demanded historic OFF/button/motion/log sources for an automation *design review*.

## Fix
- Add a distinct `rule_design_review` investigation plan, evaluated before the historical manual lockout classifier when a future automation is explicitly proposal-only. Require current targeted device, app config and actual native operation-schema evidence, with dependent-app index optional. Mark generic successful reads as **checked-unverified**; field-name receipts cannot prove trigger/action values.
- Add a fail-closed `rule_design_claim_guard` at the rule proposal answer boundary. Remove known unsupported positive claims of combined `hub_set_rule` capabilities, automatic overnight support, guaranteed lockout independence or imminent rule creation. Append explicit planning constraints: timeout-or-event distinction, 10 minutes continuously inactive, 23:00 entry coverage, final current time/switch/sensor guard at OFF, re-trigger/cancel semantics, and 4019's existing OFF.
- No extra MCP requests, no model round, no Hubitat write, no confirmation. Ordinary authorised rule creation unchanged.
- Preserve read findings and require live read-only retest before claiming this release fully resolves native rule-writing limitations.

## Remaining work
Replace tool-result field-name-only summaries with **sanitized typed evidence** of device identity/room/capabilities and app 4019's actual stored duration and lockout triggers, grounded in validated MCP schema. Retrieve current native RM action/condition schemas and implement verified multi-trigger proposal compilation only when supported; otherwise decline unsupported writes. The current HomeBrain deterministic rule writer supports only a bounded subset of schedules.

All three CI workflows must pass before merge.
