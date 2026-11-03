# v0.18.379 — recognise natural exact rule numbers in explicit native reads

## Hypothesis and real v0.18.378 failure

The installed 0.18.378 user acceptance request said `Read existing Rule Machine rule 4259 using hub_set_rule with operation="read" and args={"sections":["actions"]}`. Its technical receipt instead showed a broad `hub_set_rule(read,rule_id=4259)` without sections, a generic failed complete-document projection and a five-round / six-tool unresolved result (22.202 seconds user wall, 18.358 seconds provider, 0 paid rounds).

Code inspection confirms the direct-read parser only recognised `rule_id=4259`, not `rule 4259`. Therefore the matching prompt did not enter the explicit native read route. The source MCP error and ordered native action tree are still unknown; absence of sections in the broad prefetch **does not independently establish that the upstream read failed because of the omission**.

## Minimal general fix

Accept either a structured `rule_id=NNN` or ordinary `rule NNN` **only** when the request explicitly names `hub_set_rule`, `operation="read"`, and a validated sections array. Collect all recognised rule identifiers and fail closed if they conflict. Continue exact typed effect check, one nonmutating MCP call, and truthful source error / projection separation. No change to other investigations, model prompts, publication, Rule Machine authoring or the disabled delayed Internet-block writer.

## Acceptance and measurement

Regression tests replay the literal installed acceptance prompt, assert one exact `args.sections=["actions"]` read, and reject conflicting identifiers; existing malformed, missing gateway, error-redaction, duplicate-action and no-write tests remain. CI/tests must be green at the exact PR head before merging.

**Observed baseline (installed 0.18.378):** 22.202s wall, 18.358s model provider, 5 model rounds, 6 tools, 0 paid, native actions unverified, first answer not useful for requested action list. **After:** not measured until installed 0.18.379 is exercised on same prompt; design expectation is 0 model rounds and 1 exact native MCP read, *not* verified performance. Official frozen-case grounded/first-attempt percentages and Claude gap remain not measured.

## Risks and rollback

Risk: a naturally mentioned rule ID in an explicit read prompt might differ from its structured ID. Reject inconsistent IDs instead of choosing one; avoid triggering on a casual investigation question. Roll back parser extension if unexpected direct reads occur. No live Hubitat/HA writes, no new Cloud consumption by code development, and no writer enablement.
