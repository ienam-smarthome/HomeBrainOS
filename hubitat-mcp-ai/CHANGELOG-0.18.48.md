# HomeBrainOS v0.18.48 — Explain unsupported stateful usage automations without false writes

## Live failure in 0.18.47
A requested **new**, independent cumulative TV Internet budget (source TV device 4221, target Internet control 6923; existing rule 3985 explicitly protected) produced four Gemma rounds and seven **read** tool calls over ~45 seconds. The final answer was the generic `UNVERIFIED_MUTATION_REFUSAL`. Neither a write, a queued confirmation nor a usable architecture proposal occurred. A separate 46-second whole-hub audit attached with this trace did not address the new rule.

## Verified compiler boundary
The deterministic Rule Machine authoring service only accepts a bounded daily/fixed-clock/relative schedule grammar. It has no verified host-side translation for accumulated ON duration over disconnected sessions, pause/resume, persistent counters after reboots or a new allowance triggered by independently restored Internet access. The mere presence of driver commands `addTime` and `resetUsage` does not establish this behavior.

## Changes
- Generalized compound stateful-rule intake identifies explicit rule creation plus accumulator/cumulative/pause-resume semantics and reset on restored access. This is not tied to Google TV, any device ID or a rule name.
- Before contacting MCP or the model, respond with a truthful, detailed no-write architecture boundary and a proposed behavior contract; explicitly say no rule was created or queued.
- Preserve ordinary fixed-time scheduling requests, read-only diagnostics and unrelated device controls on their existing routes.
- Replay the exact user's live failure as an asynchronous request in tests; assert no MCP I/O, no confirmation, no false success, and no modification to rule 3985.
- No change to supported fixed-clock authoring, command semantics, device states or confirmation safeguards.

## Next engineering step
Implement and verify a separate Hubitat stateful controller app (or a fully validated equivalent) before enabling the requested usage rule; establish the source signal, observed active/standby behavior, manual versus automatic reset logic, persistence across reboot and potential contention with existing rules independently controlling device 6923.

This release fixes an unsupported-command failure **message and route**, not automatic creation of that unsupported rule.
