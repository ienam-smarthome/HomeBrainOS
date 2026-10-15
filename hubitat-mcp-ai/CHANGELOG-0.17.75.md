# HomeBrain v0.17.75 — Timed Internet blocking rule routing

## Live failure

The user asked HomeBrain to block the Tab S9 FE after a 15-minute interval, a workflow that previously authored a one-time Rule Machine command against an Internet-room switch (`off()` = Internet blocked, `on()` = allowed). v0.17.74 instead attempted a model-driven `homebrain_resolve_device(name="tab s9 fe", required_command="blockInternet")`, reported no device and asked what would start the countdown. This is the wrong tool/abstraction: `blockInternet` is an intent label, **not** a supported Hubitat device command.

The deterministic `RuleAuthoringService` already supports dated triggers, verified target resolution in the Internet room and the real `off()` action. But the shared orchestrator only dispatched it **after** calling the semantic task planner, and skipped it whenever the model labelled an instruction `operation="propose"`, even when the user's own prompt was an explicit scheduling command.

## Architectural fix

- Route unambiguous user-authorized scheduled actions through the deterministic compiler **before** model planning and capability discovery. An advisory planner cannot downgrade an explicit user instruction into a read-only proposal.
- Distinguish imperative timed actions from hypothetical/design questions. The latter cannot queue Rule Machine changes.
- Preserve the Rule Machine gateway availability check and duplicate-rule safeguards. Missing write access now produces an explicit read-only failure instead of falling through to fabricated device commands.
- Preserve the existing sensitive-action confirmation flow: **nothing is written until the user confirms**, and queued actions use the authoritative Internet-room switch ID and `off` command.
- Recognize imperative block/restrict/allow/unblock requests as write intent in central request classification; leave read-only questions as reads.
- New `rule_schedule_fastpath` / `rule_schedule_gateway_missing` metrics and integration regressions requiring a real, dated, verified `off()` Rule Machine proposal with no model rounds.

## Safety and acceptance

No Hubitat devices, automations, router controls or internet access were changed in this development. After installing the add-on version, enter `Block Tab S9 FE in 15 minutes`. Expect a confirmation proposal for a **one-time, timed Hubitat Rule Machine rule** targeting the unique Internet-room switch `Block Tab-S9-FE`, not a nonexistent `blockInternet` device command. The user must explicitly confirm before creating the rule. Verify duplicate-rule handling and that the installed hub's Rule Machine write gateway is enabled.
