# HomeBrainOS v0.18.51 — Route detailed Rule Machine reviews past snapshot shortcuts

## Live regression

On v0.18.50, a request to inspect Rule Machine app **4239** and verify
actual triggers, ordered IF/ELSE actions, counter state, reset conditions
and runtime readiness returned `route=scoped-app-status` in ~282ms.
Only `hub_get_app_config(includeSettings=false)` was called. This read
returned no interpretable status fields, so HomeBrain responded with
`success=false`, `status_verification=partial`, and did not inspect
any ordered native-rule actions or local variables.

## Changes

- A shared, generic `requires_rule_logic_inspection` predicate distinguishes
  deep named-rule logic reviews from ordinary "Is app X enabled?" requests.
- The API's `scoped-app-status` shortcut refuses to intercept deep reviews.
  Simple status lookups retain their fast, truthful existing behaviour.
- The separate configuration-and-sensor-health Rule Machine snapshot also
  bypasses these deep reviews; page identity alone is insufficient.
- The agent uses the model-led **read-only** investigation path with
  installed native rule, app-code and guide readers visible. It requests
  rule-health, typed variable status and any actual ordered trigger/action
  structure positively exposed by the connected MCP server.
- No tool guide or config identity receipt is promoted to proof that an
  automation executed, that a Pushover notification was sent, or that
  a usage counter accurately accrued 60 cumulative minutes.
- Tests replay the actual app 4239 prompt, verify both shortcut bypasses
  and the production agent routing, and preserve simple status/history/
  direct-control paths.

## Safety and limitations

No Hubitat rule or device mutation. Rule 4239 and unrelated old rule 3985
remain untouched. A deep route may still return **incomplete evidence** if
the installed MCP read tools do not expose the Rule Machine action list.
In that case HomeBrain must identify exactly which evidence is missing,
rather than inventing configuration details or creating another rule.

## Live follow-up

After updating the add-on, repeat the read-only app 4239 request. Confirm
`route=unified-mcp-agent` (or another read-only deep-investigation route,
not `scoped-app-status`), and inspect whether actual trigger/action and
variable reads are present. A successful config page alone is insufficient.
