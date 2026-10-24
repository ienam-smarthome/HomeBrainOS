# HomeBrainOS 0.18.95 — Device connectivity objective remains independent of rule authoring

## Live regression: 24 October 2026, release 0.18.94

The model-led read-only Bedroom 3 Mesh (device 7103) investigation took 26.163 seconds, made 11 tool calls and four free `gemma4:31b` model rounds. The live receipts showed `healthStatus=offline`, `mqttStatus=connected`, `lastSeen=12 October 01:30 BST`, and `dataAgeSeconds=162325`. Scoped device events and logs showed repeated watchdog state updates, and the agent listed drivers with `nameFilter=Tasmota`.

However its final response started **"Read-only rule design review"** and attached irrelevant Rule Machine semantics for an imaginary motion-light 23:00–06:00 OFF rule, even though the user requested **only a device connectivity root-cause investigation**. The response also incorrectly certified "in this driver's logic" without showing an installed driver source read: it had only listed matching driver identities. Its `investigation_coverage.domain` was **`rule_design_review`**, despite the original question explicitly identifying a telemetry issue.

## Root causes and changes

1. **Rule-design false positive**. The generic future-design classifier previously interpreted the combination of `automation`, `read-only` and `do not change` as a proposal. That is ordinary investigative language. Future-design mode now requires an affirmative goal to draft, plan, propose, create or review a **rule design**, not just inspect existing automation behaviour. Actual read-only future-rule proposals remain supported and no-write confirmation policy remains unchanged.
2. **Wrong historical ON/OFF causality route**. The generic causal planner expanded room/location event history and a one-round bounded command-origin pass for an offline/MQTT investigation. Connectivity root-cause questions now bypass this **switch-transition reconstruction** and use the normal iterative read-only evidence-selection loop with the 0.18.94 driver/app/upstream depth checkpoint.
3. **Unrelated app inventory counted as automation evidence**. The 0.18.94 source-depth check previously counted a general `hub_list_apps` list as proof that a controlling automation was checked. Only a scoped `hub_get_app_config` or `hub_get_rule_health` with an explicit installed app ID can close that particular *read-category* flag; actual device-to-rule linkage and execution remain distinct proof obligations.
4. **Final answer subject anchor**. For a device-connectivity investigation, the final evidence synthesizer now explicitly keeps attention on device telemetry clocks, driver and upstream uncertainties and forbids unrelated new-rule design/lighting lockout digressions. It also forbids claiming internal driver MQTT semantics without actual driver implementation evidence.

## Regression tests

Test the exact live user request, the difference between genuine future-rule requests and diagnostic questions, the correct telemetry investigation domain and temporal clock caveat, the non-qualifying status of generic app/driver inventories and the separation from historical switch-command causality.

## Scope and limitations

This addresses mistaken **objective/policy classification and final-answer contamination**. It does not prove Bedroom 3 Mesh's physical status or firmware/network root cause. A returned `hub_list_drivers` identity list is not a `hub_get_source(type=driver)` implementation read. Driver timestamp/health code, original MQTT messages, upstream device session, physical power and relevant automation execution are still unverified unless a future current-turn tool receipt establishes them. No live Hubitat devices, automations, drivers, rules or paid-model settings were modified.
