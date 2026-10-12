# HomeBrain 0.17.18 — evidence-backed OFF synthesis

- Makes final claim verification consume the existing structured OFF hypothesis assessment instead of allowing the model to omit material timer-feasibility findings.
- A newly started five-second inactivity timer cannot complete within 69 ms; the final result now states this when supported by the event and current app configuration.
- Preserves the possibility of an earlier pending timer, a different automation, and historical configuration differences.
- Bounds claims from missing Hubitat command records and avoids turning the reporting bridge into the initiating actor.
- Removes repeated identical uncertainty sentences even when separated by another bullet.
- Adds regression coverage of these behaviours. Read-only: no changes to Hubitat devices or automations.
