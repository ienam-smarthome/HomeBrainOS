# Hubitat MCP AI 0.10.446

- Check every new Rule Machine name against the live rule list before confirmation and again immediately before confirmed execution.
- Fail closed without queuing or writing when the duplicate check cannot read an authoritative rule list.
- Reject repeated create names and validate the complete confirmed group before its first write, preventing avoidable partial groups.
- Invalidate the cached app/rule manifest whenever a mutation may change Hubitat state.
- Describe the rule name, required time window, trigger count, and action sequence in the confirmation prompt.
