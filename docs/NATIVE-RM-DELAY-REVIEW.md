# Native Rule Machine delayed switch: offline review and upstream issue #575

**2026-11-03 · HomeBrainOS main baseline: 0.18.377 · Status: NOT ENABLED, NO LIVE TEST**

## Source and reproduced upstream limitation

[Hubitat-local-MCP-server issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) documents actual firmware 2.5.3.114 / Rule Machine 5.1.8 / MCP 5.1.1 refusal for a date-typed native `atDate#` trigger: its native form reports `supported:false`, and the document update fails with `Unsupported native setting type`. This justifies the existing `native_oneshot_date_field_unverified` refusal for the dated trigger path. It is an **open feature request**, not an implemented server fix. Previous issue #320 was unrelated (MQTT Import/Export).

The user supplied `native_rule_delay.py` and `test_native_rule_delay.py` as an alternative: a *trigger-less* Rule-5.1 native rule, `delayActs/getDelay` followed by `switchActs/getOnOffSwitch`, started by `hub_call_rule(action='actions')` with `scheduledJobCount` checked. All 13 original synthetic tests passed locally; those fake-hub passes do **not** verify live execution, the native actions readback shape, durability through reboot, exact due time, or physical network reachability.

Upstream's TOOL_GUIDE confirms that `hub_call_rule(action='actions')` dispatches native Run Actions; it does **not** prove the delayed action was scheduled or successfully executed. `scheduledJobCount>0` is a count of jobs in the app status and alone does not attribute an individual job to this delay or demonstrate it fired.

## Source-reviewed defects in the submitted sample

1. `(now + seconds).replace(second=0)` floors the displayed deadline before the requested duration (e.g. 10:00:07 + 15 min displayed as 10:15:00, seven seconds early). The actions actually begin after rule creation and Run Actions, making the label an estimate, not an exact execution timestamp.
2. On duplicate label, the original writer bypasses create but **runs existing actions again**, which may reset/double-start an active delay.
3. After a create timeout, finding the label makes the original writer run the uncertain child without a proven successful create response. Partial failures with a returned rule ID can leave a child unpaused.
4. A non-successful `hub_call_rule` result is ignored and may be reported as a verified start. Verifier silently tolerates a missing `triggers` field, extra actions, incomplete values and missing rule-health evidence.
5. Cleanup uses textual prefix + estimated due timestamp and deletes after five minutes; it does not verify the actual delayed action completed. This can destroy a still-pending job or a similarly named user rule.
6. Parent and duplicate lists need cursor/incomplete-inventory refusal; backup read should use the documented read gateway and its result verified after creation. Server may omit matching built-in type ID 18; in that case a missing type is a *refusal*, not proof that app 169 is safe to use.
7. A one-shot control command is a write requiring HomeBrain's explicit sensitive-action confirmation and verified device identity. The original synchronous sample has not been connected to the async MCP client or HomeBrain's confirmation and status-publishing paths.

## Tested, deliberately non-executable candidate

`scripts/native_rule_delay_candidate.py` is imported **only by synthetic tests** under `tests/test_native_rule_delay_candidate.py`. There is **no runtime import or scheduled job registration**, no add-on version change, no switch command and no live Hubitat writes.

It requires both `enabled=True` **and** `approved=True` to execute through a fake injected transport. Production `NATIVE_DELAY_ENABLED=False` and the existing 0.18.377 authoring refusal remain untouched. Exact request seconds are preserved; in-minute labels deduplicate without restarting an existing rule; incompatible typed parent, missing inventory, bad backup, partial create, missing triggers, extra action, wrong device, failed Run Actions and absent scheduled job all fail closed. Create timeout never retries or starts. Cleanup intentionally refuses pending-job deletion without trustworthy completion and ownership evidence.

**Do not wire this to production just because CI passes.** The current mock's assumed `actions=[{id, subtype}, ...]` native read representation is not yet confirmed from the installed MCP version, and `bestPracticeKey` / backup tool gateway and run response shapes should be checked with actual current read-only tool descriptions. The actual action scheduling semantics, restart survivability and device result are **not measured**.

## Path to live use

1. Read-only source step: inspect `hub_get_tool_guide(set_rule_reference)`, native form/action documentation and `hub_list_apps` instance/type pages with cursor completion. Verify the specific delay and on/off selectors and readback shape, without assuming type ID 18 can be retrieved.
2. Obtain explicit user permission for **one** synthetic, harmless virtual switch BAT. Confirm a fresh hub backup, target and operator time. Create an empty triggerless Rule Machine rule with two exact actions using the installed guide, read it back, start actions **once**, check pending jobs AND actual virtual-switch state after the interval. Record actions order, live native response and error/recovery path; do not reboot or delete any rule unless explicitly approved.
3. Only after the BAT, implement opt-in async HomeBrain integration that uses existing device-ID verification, sensitive confirmation store, timeout reconciliation, persisted intent IDs and read-after-action checks. Track pending execution by an independent source, not only scheduledJobCount.
4. Cleanup requires device-effect/terminal-job evidence plus persistent ownership, and must not silently remove existing user rules or pending actions. A reboot-survival test would be a separate explicitly approved hub operation.

**Rollback / safety:** this PR is test-only. Delete the candidate and tests to revert. There is no live add-on setting, database or rule to roll back. Future project quality claims need actual first-answer/live device tests rather than fabricated success from mocks.
