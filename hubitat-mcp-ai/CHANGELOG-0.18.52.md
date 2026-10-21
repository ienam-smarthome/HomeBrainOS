# HomeBrainOS v0.18.52 — Stop scoped status swallowing rule logic reviews

## Reproduced regression

User's v0.18.51 response again reported:
- route = `scoped-app-status`, request_class = `live-read`
- one `hub_get_app_config(appId=4239, includeSettings=false)` read
- 389 ms, `success=false`, `status_verification=partial`
- "no interpretable status fields; Enabled state, readiness, motion and
  countdown remain unverified."

The response includes no original prompt, so no one can prove which exact
wording reached the router. Previous guidance suggested a detailed
read-only "Perform a detailed investigation ..." question. The v0.18.51
deep-rule predicate was wrongly anchored to specific *opening verbs* while
the status shortcut broadly matched the word "status" anywhere.

## Systematic correction

1. Shared `requires_rule_logic_inspection` now recognises app/rule ID plus
   evidence obligations (triggers, ordered actions, IF/ELSE, variables,
   cumulative counters, reset conditions, allowance etc.), independent of
   whether the user begins "Inspect", "Perform", "What are", or "Can you".
2. `scoped_status_app_id` now accepts only short status-oriented questions,
   excluding multi-part or technical questions about actions, conditions,
   variables, counters, reset logic or execution. Replacing a one-off phrase
   patch with an explicit status-only boundary addresses differently-worded
   versions of the same request.
3. At the API level, **both** the `scoped-app-status` shortcut and the
   generic automation-inventory shortcut independently check that deep
   Rule Machine logic inspection is not required.
4. A true short status-only request that returns no configuration status
   fields additionally checks the installed native Rule Machine
   `hub_get_rule_health` read-only endpoint when available. It reports only
   positively observed paused/stopped/broken booleans, never infers from
   labels or upgrades health to proof of execution.
5. The legacy fallback for a simple status query no longer mentions
   "motion and countdown" for arbitrary native apps. An app config read
   with no supported enabled/paused fields is accurately described as a
   partial config-only read.
6. Tests replay the prior v0.18.51 detailed prompt, short-form variants,
   simple app enabled-status questions and an actual API dispatch with
   the broad inventory matcher intentionally forced to true.

## Remaining evidence boundaries

This improves *routing*; it does not magically expose the ordered
Rule Machine trigger/actions if the installed MCP server cannot read them.
The model may still report specific missing evidence, and it must not
claim verified 60-minute behaviour solely from a variable or app-identity
page. A timed controlled test remains necessary for verified runtime
blocking and reset behaviour.

No Hubitat reads or writes were performed during development. Neither
app 4239 nor existing rule 3985 was modified, enabled, disabled or paused.
