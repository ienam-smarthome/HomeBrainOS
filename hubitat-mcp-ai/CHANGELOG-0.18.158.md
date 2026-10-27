# HomeBrainOS v0.18.158 — Last-contact anchored causal investigation

Live comparison on 27 October:

- A separate detailed investigation found a plausible self-disconnection
  loop: a 12 October nightly power-saving OFF command, a following confirmed
  switch=off report, later loss of connectivity and failed attempts to turn
  the plug on again. A physical AP association was **not** independently
  established by that report.
- V2.157 read 20 recent rows and an app config for issuer #3103 but obtained
  **no** typed app settings and hit the model's 15-second planning timeout.
  Its 5-page identity inventory took 19.459 seconds, mostly MCP-page time.

## Change

1. **Historic contact anchor.** When current verified device metadata contains
   an old, parseable `lastSeen`, V2 can propose one additional bounded
   read around that timestamp if the returned event history starts much later.
   The request is scoped to the independently verified device, subject to the
   actual live MCP read-op/schema, host read plan, effect, time/read limits,
   and no implicit write permission. Prefer a ±2h `since/until` request
   if allowed; else a larger bounded history page. A backend that ignores
   time filters, a retention limit, or an empty page **cannot** establish
   that no events occurred. The reported `lastSeen` is an information-seeking
   lead, not proof of genuine physical contact.
2. **Request controller settings.** The independently evidenced issuer's
   existing read-only `hub_get_app_config` request now includes
   `includeSettings: true` when permitted by the live argument schema.
   Never invent unsupported fields or bypass the normal scope/read validator.
3. **Distinguish read success from information gain.** Bootstrap diagnostics
   now record `settings_projection` as `typed_fields_available`,
   `readable_no_supported_fields` or `settings_not_readable`, as well as
   the number of supported typed fields. A read that returns no useful
   structured values does not prove configuration or historical actions.
4. **Bounded causal model budget.** The 15-second timeout prevented every
   previous explanatory investigation from returning a plan. Causal
   questions now receive at most 35 seconds for each model planning round;
   factual status and history paths still do **zero** model planning.

## Limitations

This is still an explicitly opted-in, read-only investigation prototype.
It cannot independently ping equipment or retrieve router associations unless
safe, live-declared evidence tools are added. A Tasmota MQTT broker session
is not a proof of plug contact. Even a valid switch=off report is not
proof that the plug powered off its own AP; that requires corroborating
network topology or physical observation.

The source may not retain October 12 history; the historical anchor is
a bounded attempted read, not guaranteed access. App #3103 may have
settings outside the existing allowlisted typed projection. Neither
model timeout nor causal accuracy is guaranteed to improve merely by
lengthening the budget.

## Live acceptance test

Repeat the Bedroom 3 Mesh investigative question with 0.18.158 and inspect:

- `bootstrap_diagnostics.history_last_contact`: whether it attempted
  a bounded historical query and oldest returned timestamp.
- `coverage`: `since`, `until`, `hoursBack` and source completeness.
- `bootstrap_diagnostics.controller_config`: confirm
  `settings_requested=true` and whether any typed settings were returned.
- `planning_diagnostics`: determine whether 35s allowed a structured plan,
  including any new source reads, versus merely a longer timeout.
- `reads_executed`: count only authorised source reads, not a speculative
  root-cause claim.

No production rule/app/driver, live device or write capability changed.
