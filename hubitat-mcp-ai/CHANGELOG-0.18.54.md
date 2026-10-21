# HomeBrainOS v0.18.54 — Keep targeted Rule Machine reviews out of global System Check

## Live regression

After upgrading to v0.18.53, the attached live response used
`route=comprehensive-system-audit` and scanned 205 devices, 156
automations, 273 scheduled jobs, and capped logs. It did NOT query the
targeted native-rule health/variable operations for apps 4239 and 4241.
Its optional AI advisory explicitly noted that those two rules' data
was missing from the audit.

The user's **exact submitted text is not present in this telemetry**, so
we cannot identify the single predicate responsible in that run. The
immediately preceding suggested test requested a narrow read-only
verification of Rule Machine apps 4239 and 4241 with cross-rule counter
references, Hub Variable, devices 4221/6923, actions and history.

## Architectural correction

- Add independent scope classifier with bounded named app-ID extraction.
  Recognizes "Rule Machine apps 4239 and 4241", "app ID 4239" and named
  coordinated IDs while refusing to treat TV/Internet device IDs as apps.
- A specific rule's triggers, actions, variables, health, history and
  reset mechanism take priority over the whole-hub System Check, even when
  the question also mentions Hub Variable, devices, logs and scheduler.
  "Hub Variable" is not explicit whole-hub audit intent.
- Apply the same scope boundary in the cross-domain audit policy, broad
  automation diagnostic policy, comprehensive-audit policy and API
  dispatcher. No independent shortcut is allowed to undo the intended
  route.
- Genuine explicitly whole-hub checks ("audit my entire Hubitat hub",
  "review all automations and devices") retain their deterministic
  comprehensive audit route, even when named rules are included as samples.
- Extend the deep rule-review predicate to coordinated plural IDs, and
  prefetch native health and local-variable evidence for each of up to 3
  specified Rule Machine apps rather than only the first ID.
- Preserve read-only authorisation, request deadlines, exact-ID evidence
  boundaries and structured confidence calibration. Existing rules 4239,
  4241, 3985 and control devices remain unchanged.
- Regression tests replay the previously recommended app 4239/4241
  verification and prevent any call to the whole-hub audit function;
  separate tests protect genuine full-system diagnostic routing.

## Remaining verification

Correct routing cannot prove the actual logic of rule 4239 and companion
reset rule 4241. Once installed, their native health/variables, ordered
conditions/actions and command histories must be inspected. A local variable
of 4239 cannot be assumed controlled by another app merely by name; verify
whether `TV_Minutes_Used` is a shared Hub Variable or another supported
reference. A report of a different paused legacy rule is not evidence that
4239 or 4241 is paused.

## Live retest

"Perform a read-only verification of Rule Machine apps 4239 and 4241.
Read their native rule health and local variables, compare the exact
`TV_Minutes_Used` variable references, verify the one-minute delay and
60-minute block mechanism, check device 6923 command history, and state
what remains unverified. Do not change anything."

Expected route: `unified-mcp-agent` (or another scoped named-rule
investigation, never `comprehensive-system-audit`). The evidence should
contain targeted app 4239 and app 4241 reads.
