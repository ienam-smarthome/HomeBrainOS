# HomeBrainOS v0.18.55 — Evidence-calibrated native Rule Machine conclusions

## Live regression

The v0.18.54 read-only investigation finally reached both Rule Machine apps
4239 and 4241, read native health (stopped=false, broken=false), enumerated
zero local variables, read Hub Variable TV_Minutes_Used and two app pages,
and requested 24h device event history for Internet control 6923.

However, the model concluded "verification ... is complete" even though
the structured assessment had evidenceComplete=false and command_history
missing. Its device-event receipt contained 16 truncated records comprising
usageStatus, dailyUsedMins and sessionMins for only a few observed minutes.
A requested hoursBack=24 is not proof of an entire 24-hour command history,
nor evidence of which app issued OFF. The response also stated cross-app
variable synchronization was verified merely because source=hub existed,
while its hypothesis section still treated "local-only variable" as live.

## Fix

- For successful hub_get_variable reads, retain the exact requested name,
  verified source (including source=hub) and safe numeric value in a bounded
  structured receipt. Reject mismatched returned names. Arbitrary strings
  and secret-like numeric names are excluded.
- Add an evidence-claim guard scoped to **named native Rule Machine reviews**.
  It reconciles an "investigation/verification is complete" headline with
  explicit incomplete source coverage.
- A bounded or truncated device-event page cannot support an absolute "no
  OFF commands from app X in the past 24h" statement or producer attribution
  from driver telemetry. Report **threshold execution unverified** instead.
- The existence of a global Hub Variable is not proof that two different
  Rule Machine compiled action trees target it; require independent typed
  cross-app reference proof before confirming exact synchronization.
- Once source-qualified hub-variable evidence exists, do not repeat the
  incompatible hypothesis that the same variable exists **only** as a local
  app variable. Other candidate causes (e.g. missing one-minute execution)
  remain to be tested.
- Retain supported facts such as the numeric counter and native health states
  instead of replacing an entire technical answer with a generic refusal.
- Regression fixture reproduces the supplied v0.18.54 narrative and receipt
  scope, with negative controls for complete evidence and genuinely global
  audits.

## Limitations and safety

This release does not yet prove the actual 60-minute block, cross-rule reset,
cancelable one-minute delay behaviour, or any command's initiating app.
An ordinary driver sessionMins value is independent of the Rule Machine
counter. A full native, attributable command history remains necessary to
make an exclusion claim for the whole 24-hour window.

Code and tests only; live apps 4239, 4241, legacy 3985 and devices 4221,
6923 remain unchanged. No rule creation or blocking is authorized by the
new claim validator.

## Live re-test

Read-only inspect apps 4239 and 4241 and Hub Variable TV_Minutes_Used.
Verify the exact variable reference and condition/action branches using
native Rule Machine app read capabilities, then request a bounded explicit
command-off history for Internet device 6923. Separate a returned page's
actual oldest/newest event timestamps from the requested hoursBack window.
If command history remains incomplete, state that blocking attribution is
unverified rather than "not observed in 24 hours".
