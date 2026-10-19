# HomeBrainOS v0.18.42 — Candidate scheduler/app identity reconciliation

## Live v0.18.41 verification
The comprehensive read-only audit completed with 205 devices, 152 normalised automations, 200 capped log rows and a real 271-entry scheduled-job collection in about 36.1 seconds. Jobs included 52 `sendEventReminder`, 28 `deviceHealthCheck`, 28 `sessionTick` and 17 `midnightResetJob`. However, the live scheduler source had **zero rows with explicit recognised owner fields**, so a scheduler-key candidate such as `app3950` cannot automatically be treated as a verified app owner. The report did not cross-check candidate identities with the already retrieved installed automation inventory.

## Change
- The existing comprehensive System Check now retains a **bounded, minimal identity index** of current installed app/rule IDs, names, types and normalised configuration statuses (not source code, raw settings or secrets). No additional MCP reads.
- Compare positive numeric app-ID candidates decoded from exact scheduler-key patterns against the same-audit installed-app identity index; return matched, unmatched and reported disabled-state candidate counts.
- Show at most six disabled-configuration ID matches and label each as a **candidate only**. Matching an ID does not prove a disabled rule's schedule remains installed, that it executed, or that its callback is wrong. An unmatched key does not prove an app is absent, especially when either inventory is incomplete.
- Report the remaining verification obligation: obtain authoritative callback ownership, compare actual triggers/actions and common target device IDs, inspect enabled/disabled behavior, then consider overlap. Do not propose changes merely because names or timestamps look similar.
- Preserve all existing devices/logs/queue evidence, the intentionally unpowered SenseCap D1 option and Free Gemma as the default. No Hubitat writes, no new MCP privileges, no paid model changes.
- Tests cover matched/missing app IDs, disabled candidates, missing sources, partial inventory, untrusted labels and final report wiring.

## Important limitation
This phase is identity-level correlation only. Neither the MCP scheduler response nor the existing app list provides trustworthy action-target dependencies without separately reading relevant rule/app configurations. Future targeted, permissioned **read-only** MCP investigation is needed before claiming redundant lighting rules, broken heartbeats or disabled app callbacks.
