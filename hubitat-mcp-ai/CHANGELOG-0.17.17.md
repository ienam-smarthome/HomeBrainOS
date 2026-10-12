# HomeBrain 0.17.17 — OFF causal hypothesis evaluation

- Adds a reusable, structured evaluator of competing OFF explanations without promoting unverified actors to likely causes.
- Distinguishes the reporting bridge from the actor that originated the command.
- Compares inactive sensor edges with the currently configured inactivity delay, including milliseconds, seconds and minutes.
- Explicitly identifies when a new timer started at a recent inactive edge could not yet have expired. Earlier scheduled timers remain possible.
- Does not assume the current automation configuration was necessarily in force at the historical time.
- Preserves uncertainty when command history is bounded, app logs are empty or a physical control has no recorded event.
- Adds regression tests including the 69 ms OFF proximity versus the configured five-second inactivity delay.

This is a read-only reasoning improvement. No Hubitat settings, automations or devices are changed.
