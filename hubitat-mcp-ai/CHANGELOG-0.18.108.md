# HomeBrainOS 0.18.108 — Verify implemented behaviour before treating raw settings as causes

## Motivation: Claude/HomeBrain comparative investigation (25 October 2026)

Claude read the configured Livingroom Light 1 automation topology and identified the FP400 activation source, Linptech Kitchen and Matter LWR01 keep-on sensors, repeated sensor activity, a 30-second all-inactive OFF delay and a five-minute backup-OFF check. The user's screenshot of installed Light Mode Controller app 4019 confirms these effective UI settings. It does not prove which sensor historically held the light on.

HomeBrain 0.18.107 instead inferred from a raw stored value `inactiveAction = "none"` that the app was expressly configured never to switch the light off and recommended changing the setting. It did not inspect the installed Groovy implementation or reconcile the effective configuration and configured sensor identities. That conclusion conflicted with the Hubitat UI.

## Changes

- **Single evidence-driven semantic follow-through:** During a read-only investigation, when a successful installed-app configuration read exists and the model attempts to explain runtime behaviour from a raw property value without a matched source read, give the AI **one** bounded opportunity to inspect the real installed implementation. Reuse the existing Groovy source workbench, allow only read-only capabilities, respect the model tool-round budget, and let the model choose the read. App IDs come from typed receipts; no hard-coded rule/device topology or keyword-to-tool routing.
- **Evidence-aware final answer:** A source-absent configuration interpretation can no longer be stated as a verified mechanism or a proven reason to change the setting. The existing synthesis validator replaces only the unsupported inferential paragraph and matching configuration-change prescription, preserving unrelated observations, activity timelines and candid uncertainty. As before, a bounded no-tools repair may produce a better evidence-grounded final answer.
- **General investigative skill:** Explain that stored properties, displayed effective app settings and actual Groovy branches are different kinds of evidence. Trace activation sensors, keep-on sources, timers and fallback/watchdog code separately and use historical events to test proposed causes. No user-specific topology is encoded.
- **Metrics and tests:** `configuration_semantics_source_retry` records a source-seeking round without private prompts. New synthetic replay tests use app 4019 and a completely unrelated hypothetical app/property, check source ID and installed app ID distinctions, preserve Markdown timelines and prevent unsafe setting advice without code.

## Limits

Reading implementation is necessary but not automatically sufficient: HomeBrain must correctly interpret relevant methods and confirm any claimed current/historical behaviour with supported runtime data. This release doesn't modify live Hubitat app settings, devices or rules. It does not turn the kitchen/hallway sensor activity into proof of which sensor held the light on during 20:23–00:41. The user should re-run the same read-only investigation to measure improvement. No paid-model routing changed.
