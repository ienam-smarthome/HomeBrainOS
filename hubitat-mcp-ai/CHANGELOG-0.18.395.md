# HomeBrainOS v0.18.395 — readable, source-grounded native Rule Machine descriptions

## Live baseline

The user created "One-off block TV" (Rule Machine ID 4285) **as a test rule**. A live v0.18.394 named-rule read succeeded in 548 ms via `hub_list_rules` then `hub_set_rule(operation="read")`, returning three ordered actions, 71 settings (6 redacted/unsupported), and one trigger. However the first answer dumped the editor setting keys rather than explaining the saved action sequence.

The source supports: a saved trigger configured at 08:00 (no date verified), Switch OFF on device 6923, a wait with the saved minute field of 15, and Switch ON on device 6923. It does **not** establish that the rule is one-time, that it has a currently scheduled job, that it executed, or that physical Internet reachability changed. The rule is a user-created **test**; this PR does not edit or run it.

## Change

- A generic privacy-filtered native Rule Machine summary renderer groups typed, ID-matched configuration fields by saved trigger/action ID and renders a short, natural-language description.
- A saved ON/OFF direction requires a typed boolean and source-backed Switch device IDs; a wait duration requires a matching typed `hrs:min:sec` selector and numeric fields. Unknown native methods and conditional branches remain explicit uncertainties, not invented commands.
- A **dated one-time** trigger is claimed only when a typed `date#=true` and valid `atDate#` are both in the same trigger; a mere rule title or `atTime#` does not imply one-time. No inference of recurrence from an empty date field either.
- Exact quoted named-rule requests use the compact summary after the original native section read and source projection. Explicit `hub_set_rule operation=read sections=[...]` technical requests retain their detailed field-by-field output.
- No extra MCP calls, AI rounds, provider subscriptions, or live mutating operations. Native raw credentials and unsupported settings stay excluded.

## Verification and limitations

Synthetic cases cover OFF/wait/ON chronology with unrelated device IDs, date flag proof versus absence, missing targets, unknown methods, conditional uncertainty, redaction and source ID checks. The existing read-only native section tests must remain green. Full CI results in the PR. Live **first-answer improvement, real response timing, scheduled execution success, actual network effect and broader model quality NOT MEASURED** until a fresh version-paired comparison.

## Safety / rollback

Only read-only projection and presentation. No live Hubitat or Home Assistant rules, devices or router controls were changed. Revert this patch if the summary misstates stored semantics, leaks settings, or hides a partial-source failure. The previous raw projection remains an explicit diagnostic option.
