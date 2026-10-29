# v0.18.233 — Follow controller commands upstream to their decisions

## Live regression

The 29 October heating test now describes the controlled shutdown naturally
(v0.18.232, 25.2s rather than 46.6s), but it **still** does not discover
why the Smart Thermostat Scheduler decided to remove demand. Claude did:
radiator target satisfaction and the scheduler's minimum hold interval.
The V2 model had not read the controller's historical INFO decision logs,
and its 14s final synthesis did not return a publishable hypothesis.

## Changes

- Introduce **evidence-led upstream controller reasoning**. A model that
  already retrieved a target device's incident-time command provenance now
  sees a bounded suggested app-specific historical log READ for the
  *independently attested* issuing app, around its source event. The model
  chooses any READ; no host-performed extra query or new tool permission.
- Distinguish *what the actuator did* from *why its controlling automation
  decided to act*. Configuration-page metadata is not historical execution
  evidence. The planning policy directs the model to inspect historical app
  decision inputs and linked sensors where supported.
- Preserve scoped INFO app-log messages for a model-selected, verified
  appId. Generic unfiltered log reads continue to receive the established
  WARN/ERROR-focused projection. Other applications' INFO messages are
  excluded, and message text passes existing safe_string redactions.
- Join source-attested app command history to app-specific execution log
  entries only when the source IDs agree and the source clocks are within
  a bounded incident-proximity window, allowing UTC/UK summer-time
  ambiguity without claiming a verified timezone.
- Give final reasoning and in-loop proposal verification independent
  receipt-backed log-message anchors. The host still rejects fabricated
  app IDs, missing/altered event references, unverified numbers, and
  unsupported confirmed physical root-cause claims.
- The evidence packet now reports the number of relevant controller
  decision-log observations. These are *reported* app decisions, not
  independent physical confirmation of the attached sensors.

## Safety and evaluation

Read-only MCP effect guards, live operation contracts, source-ID validation,
no-write mode and published certainty limitations remain in place.
Tests cover source-attested app discovery, properly-scoped INFO reads,
cross-app privacy boundaries, citation validation and end-to-end model
selection of the next app-log READ.

Live validation must still show that V2 actually retrieves the scheduler
decision logs and independently investigates TRV measurements; successful
unit tests alone do not prove Claude-equivalent reasoning.
