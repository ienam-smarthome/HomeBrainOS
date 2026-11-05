# HomeBrainOS Hubitat MCP AI v0.18.417

## Why

The installed v0.18.416 test requested read-only inspection of saved dated-trigger fields on existing native Rule Machine rules 2967 and 3985. The request was routed into the model-led `existing_rule_verification` domain instead of the deterministic `native_dated_trigger_discovery` reader. Both unpaged native reads failed; the bounded paged reader added in 0.18.416 was not attempted. This is a routing failure, not evidence of missing dated triggers or corrupted rule documents.

## Change

- Recognize positive read-only investigations of *existing* native Rule Machine `dated-trigger fields` and `native Rule Machine rules`, retaining the original narrow safety/intent requirements.
- Regression replay requires both explicitly requested IDs to pass through the specialist reader and separately invoke bounded, revision-checked paginated reads after a failed whole-document read.
- Generic action-tree audits and prospective rule creation do not match the specialist request.
- Native rule authoring remains disabled; no editor form, router/device control, permissions change or Hubitat writes.

## Boundaries

CI confirms only repository and simulated-source behavior. Live Hubitat source pagination and the parent/type/dated creation contract remain unverified. The paused state of rule 3985 is source-attested in the earlier generic health receipt but cannot be used as proof of an enabled dated trigger. Retest installed 0.18.417 with Technical JSON before any additional authoring work.
