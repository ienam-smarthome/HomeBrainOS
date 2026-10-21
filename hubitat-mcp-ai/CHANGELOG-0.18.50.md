# HomeBrainOS v0.18.50 — Review existing automations before conditional creation

## Live regression from v0.18.49

The user asked to create a cumulative 60-minute Google TV Internet rule **only
if** an existing rule ("Internet: Google TV block after 1hr total TV-on time")
did not already implement the behaviour. HomeBrain made three successful
read-only calls (list apps, fetch app 4239 configuration, list its local
variables) and no write calls. It returned the misleading generic
"I could not verify that this action actually ran" despite never attempting
to execute the conditional action.

## Correction

- Detect the full "first inspect the existing rule; if it already works, do
  not create a duplicate" instruction as a deliberate **read-only review
  stage**, not an immediate instruction to create.
- Prevent "do not create a duplicate" from being treated as a prohibition on
  investigating the existing rule. Keep independently requested writes on
  their existing approval path.
- Expose only currently installed read-only MCP tools in this stage, and
  reapply that restriction after tool discovery and before model rounds.
  No Rule Machine write gateway can be used.
- Tell the model to inspect the actual installed rule, including triggers,
  ordered actions, variables and status. Reading an app's identity page or
  a variable list alone does not prove the intended rule actually works.
- Preserve supported review findings in the final answer instead of
  suppressing them under the blanket "no mutation receipt" safeguard.
  If a generated answer falsely claims a change, return a safe no-write
  notice instead. Results of this stage are labelled **live-read**.
- The existing-rule inspection remains incomplete until real action/trigger
  evidence is read; an incomplete read cannot automatically justify creating
  a replacement rule. Later writes still need a separate proposal, exact
  device validation, duplicate/conflict review and explicit confirmation.
- Keep the original v0.18.49 direct-creation capability preflight unchanged
  for actual unconditional cumulative-rule authoring.

## Safety

No Hubitat app, device, rule 3985 or rule 4239 is created, paused, enabled,
disabled, unblocked or otherwise changed by this code update. It does not
perform live Hubitat integration tests. A successful full repository test
suite demonstrates routing and guard behaviour only, not the operational
correctness of the existing cumulative allowance rule.

## Live retest

Ask: "Read-only review of the existing 'Internet: Google TV block after 1hr
total TV-on time' Rule Machine automation. Verify the actual 1-minute
trigger, conditions, ordered IF/ELSE/actions, global counter and reset on
Internet-control OFF. Identify app ID, status and missing evidence. Do not
create, edit, enable, disable or pause anything."

Compare the rendered evidence with Hubitat's native Rule Machine app page.
Never create an additional rule merely because app configuration metadata
does not include a readable action tree.
