# Hubitat MCP AI 0.10.454

## Reasoning hardening

This release hardens the general evidence-reasoning architecture introduced in 0.10.453 without adding new user-question phrase routes.

- Current-turn MCP/tool results are now the only evidence allowed to support live or historical factual claims. Earlier assistant replies remain conversational context only and cannot be reused as proof unless this request independently verifies them.
- Read-only investigations have a soft generic reasoning budget: up to 3 model tool rounds and 8 model-directed read executions. Once spent, HomeBrain keeps the evidence already gathered and forces synthesis instead of continuing an open-ended tool hunt. Mutation/confirmation executions are not rejected by the read budget.
- The obsolete causal sensor-hunting host hint is removed before provider calls. Causal questions now use the same evidence-sufficiency contract as every other read, including the rule that correlation is not proof of causation.
- Provider turns with no callable tools receive the full current-turn final-synthesis contract even when the legacy orchestrator final-answer helper supplied a shorter instruction.
- Supported numeric aggregate queries such as power, battery, temperature, and humidity now prefer the complete `hubitat://context` bulk live-state resource instead of a slow full `hub_list_devices` inventory. Partial/unavailable context still falls back to the complete inventory path.
- Device-history target resolution now distinguishes a genuinely missing device from an ambiguous one. When an exact multi-word label filter finds nothing, it performs one bounded broader targeted lookup using the final identifying token and surfaces the resulting candidates instead of silently choosing one or loading the complete inventory.

## Live issues addressed

The changes are driven by 0.10.453 live testing where open-ended investigations reached 19-30 tool calls and 59-76 seconds, a power ranking paid about 31 seconds for a full inventory read, a history lookup for `bathroom fan` collapsed a zero-candidate result into the misleading message `device could not be resolved uniquely`, and one answer reused unsupported historical detail despite lacking current-turn event-history evidence.

## Compatibility

Simple one-tool deterministic reads retain their fast presentation path. Native Ollama thinking remains enabled for supported reasoning model families, provider thinking traces remain private, and all existing confirmation/mutation verification rules remain authoritative.
