# HomeBrainOS v0.18.68 — Confirmed Rule Machine create timeout and read-only reconciliation

## Live incident, 22 October 2026
The user authorised the single native `hub_set_rule` creation of **Livingroom Light 1 – Night Idle OFF – TEST** after v0.18.67 correctly queued a confirmation. Preflight verified device 7805, FP400 motion 7978, 40 named Rule Machine rules, and the current action guide. The confirmation then submitted six triggers and seven actions with `confirm:true`.

At **25,008 ms**, the MCP client raised **`ReadTimeout`**. HomeBrain reported an unverified write and no app ID. **The user immediately supplied a Hubitat Rule Machine UI screenshot showing the installed rule and its six triggers/seven actions**, including both clock guards. The screenshot verifies existence/current structure, while it cannot prove the entire native creation receipt or future runtime behaviour. The clock condition displayed FALSE at ~14:14 because it was outside 23:00–06:00; this is expected. The light was OFF at the time and app 4019 may still intervene earlier than the requested 10-minute delay.

## Root cause
The MCP HTTP client has a normal 25-second read timeout. Native rule creation can be committed by Hubitat before the upstream response is delivered. A client-side timeout does **not roll back** the server-side write. Treating that timeout as proof no rule was created risks accidental duplicate active automations. No second native write should be dispatched.

## Fix
- Extend only the **HTTP read timeout** of a confirmed *new-rule* `hub_manage_rule_machine -> hub_set_rule` call from the normal 25s to at least 90s. Preserve original connect/write/pool timeouts and leave all other calls unchanged. Never replay a confirmed mutation even if a tool's annotation incorrectly advertises a read-only hint.
- If a confirmed new-rule write still returns an HTTP transport failure, run **one read-only** `hub_read_rules/hub_list_rules` reconciliation for the exact queued rule name. Do not resend `hub_set_rule`.
- Distinguish four cases: exactly one matching named rule (report current presence and any returned ID, but **not** full write or runtime verification), multiple matches (possible duplicates), confirmed complete list with no matching rule (outcome still uncertain, commit may be in flight), missing/failed/incomplete rule inventory (outcome unknown). Never use gateway metadata as an empty inventory.
- Preserve sequential execution safety: no later confirmed actions run after a timed-out create. Explain skipped actions if the original group had more than one item.
- Classify timeout reconciliation outcomes as **unresolved** rather than green success or a categorical failed Hubitat creation. Log the original write receipt and the second read receipt separately.
- Regression tests cover exact-name presence, no match, ambiguous duplicate names, metadata masquerading as inventory, original non-transport errors, strict no mutation replay, targeted HTTP timeout scope and accurate outcome classification.

## What this does not do
This release does **not** create or modify the user's existing rule. It does not prove that the ten-minute cancellation works at runtime or change competing app 4019. Hubitat UI/Rule Machine logs must be used to verify rule app ID and actual scheduled execution on or after the first test window. The original 2026-10-22 confirmation already sent a mutation; do not submit the create request again.
