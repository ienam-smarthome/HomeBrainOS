# 0.16.164 — Clear lighting-rule explanations and bounded mode-event correlation

- Preserve authoritative command-to-device attribution (producing Rule Machine app and sub-second state confirmation).
- Clean Rule Machine editor text: skip malformed Hubitat field serialization and remove transient `(T)`, `[TRUE]`, and displayed numeric comparison values that do not establish historical evaluation. Preserve triggers, thresholds, actions and sensor labels.
- Distinguish configured triggers from conditions/actions; explicitly note that current configuration does not prove historical execution.
- When app execution logs lack an aligned mode trigger and the actual command producer's configuration includes a mode-change trigger, perform one additional bounded read-only hub-wide mode-log query for the same 18-second time window.
- Match only timezone-qualified, timestamp-aligned transitions to modes configured in that rule. Report matches as independent correlations, not proof of what the rule evaluated.
- If relevant mode logs are absent, incomplete or timezone-ambiguous, retain the unverified-trigger caveat and never invent a mode change.
- Preserve the read-time offline sensor/parent caveat, separate from claims about historical inputs.
- Regression tests cover raw UI artifacts, transient condition flags, bounded time/correlation checks and no-provider causal finalization.

The additional mode-log read is restricted to proven lighting automation ON commands with an explicit configured mode trigger and no same-app mode execution log. Strictly read-only.