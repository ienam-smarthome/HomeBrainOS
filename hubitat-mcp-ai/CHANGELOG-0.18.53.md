# HomeBrainOS v0.18.53 — Native Rule Machine evidence before interpretation

## Live regression

Read-only app 4239 investigation finally reached `unified-mcp-agent` in v0.18.52, and retrieved configuration for 4239 and companion reset rule 4241. It returned nine Gemma rounds in ~61 seconds. The prose described an event-driven one-minute delay/increment loop, a counter reported as 42, and a reset rule; however, the supplied evidence summary lacked direct native rule-health or variable receipts and the report labeled itself "complete" while `investigation_coverage.evidenceComplete=false`.

One model-proposed write was safely blocked (`read_only_model_write_blocked=1`). The report said `hub_get_rule_health` was blocked by the gate, but the evidence doesn't identify which model proposal was rejected; do not attribute that write-block to a particular operation.

## Changes

- At the start of every detailed read-only named Rule Machine investigation, if the **installed** read gateway is present, call only two predeclared read leaves: `hub_get_rule_health` and `hub_list_rule_local_variables`, bound to the *requested* app ID.
- Record source-scoped evidence receipts including observed `paused/stopped/broken` boolean fields and bounded numeric local variable values, while filtering arbitrary string values from model-visible packets.
- Pass a compact typed evidence packet to the model before exploration so it does not need to guess which gateway implements the native health/variable readers. Failed/unavailable reads remain explicitly unknown, never "paused" or "broken" by inference.
- Warn explicitly that similarly named LOCAL Rule Machine variables cannot be assumed shared across apps. Companion app 4241 must have verified global Hub Variable or equivalent cross-app mechanism before one claims it resets app 4239's local counter.
- Clarify that one initialization log is not proof of minute-by-minute rule execution.
- Correct final headline "investigation ... is complete" to "remains partial" when the user's deep-rule investigation has explicit incomplete source coverage; retain useful evidence and counter values.
- Tests cover a 42-minute numeric counter, false and null health booleans, unavailable reader, secret-like string exclusion, zero write operations and cross-source completeness calibration.

## Limitations

- Code/test changes only. No access to the user's live Hubitat hub; no Rule Machine writes, device commands or scheduler changes.
- The native MCP server may not expose the named health/variable read leaves for every installation. In that case the packet reports failed evidence, and the model must use other independently advertised READ paths.
- Rule Machine configuration paragraphs may indicate intended trigger/action sequence but cannot by themselves verify actual execution, command dispatch, Internet reachability or variable-reset cross-app semantics.
- The new hook is scoped to named detailed investigations and does not change ordinary status requests or Rule Machine write approvals.
- Existing rules 4239, 4241, 3985 and the independent Groovy controller remain untouched.

## Next authorized live acceptance check

After upgrading to v0.18.53, inspect app 4239 and verify the two native read receipts. Then check whether the counter is a global Hub Variable or truly local, and whether app 4241's reset targets exactly that shared instance. Collect device 6923 OFF command/state history before claiming a 60-minute lockout worked in production.
