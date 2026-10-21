# HomeBrainOS v0.18.49 — Capability-driven stateful Rule Machine authoring

## Why

v0.18.48 treated compound usage allowance rules as categorically unsupported.
A competing implementation demonstrated that a native Rule Machine rule can
use periodic triggers, Hub Variables, nested IF/ELSE actions, arithmetic,
Internet-control switch OFF and a counter reset. That result is a useful
reference, not proof every Hubitat MCP version exposes identical shortcut
schemas.

## Changes

- Replace the unconditional 9 ms "unsupported controller" rejection with
  a scoped, **read-only live MCP tool-guide preflight**: native Periodic
  Schedule and device-state triggers, native conditional and variable
  actions, variable conditions and hub variable reference must all be
  positively advertised by the installed server.
- Route the explicitly authorized stateful-rule request to the normal model
  tool-calling process using the actual installed Rule Machine guide and
  dynamic addAction/addTrigger discovery. Do not assume a single static JSON
  syntax where Hubitat's version-specific wizard may differ.
- Add an independent, host-side topology gate to reject incomplete proposals
  before confirmation, including missing minute trigger, missing switch-OFF
  reset trigger, lack of variable math/reset, unmatched variable names, broken
  IF/END-IF structure, absent switch-OFF action and changes to an existing
  rule. The ordinary general Rule Machine validator still applies.
- Ensure missing capability evidence gives a specific **no-write** response,
  and a model that provides only prose cannot claim a rule was queued.
- Preserve existing permission gates, live ID validation, duplicate-name
  checks, Rule Machine approval and execution confirmation; no Hubitat writes
  are run by these repository changes.
- Regression test the original user prompt and Claude's natural wording,
  guide availability, disabled write tools, complete/partial example plans
  and ordinary unrelated schedules/read-only questions.

## Known limits

- This release changes *proposal capability*, not live Rule Machine state.
- A guide confirming an available shortcut is not a guarantee that the
  resulting rule will save. The hub's typed gateway response, rendered
  configuration, app history and controlled timer trials remain authoritative.
- The host topology gate is conservative. A valid alternative architecture
  with several smaller rules may be rejected unless separately implemented
  and verified.
- The one-minute counting resolution is approximate, not precision
  continuous timing. The extra Internet-OFF trigger is required to prevent
  the reset race if a block is quickly followed by an unblock.
- The existing rule 3985 and the separate standalone Groovy app remain
  unchanged. No automatic pause, removal, duplication or enablement.
- No live connected Hubitat MCP execution was performed in this PR.

## Acceptance test

Ask HomeBrain to create a **new** cumulative 60-minute TV-on Internet rule,
verify it reads the live Rule Machine guide, obtains the correct device IDs,
and presents a complete structured confirmation proposal instead of claiming
it is unsupported. Only after approval should a confirmed create be attempted
and verified in the Rule Machine UI. Run controlled elapsed-time, rapid
unblock and conflict tests before relying on access restrictions.
