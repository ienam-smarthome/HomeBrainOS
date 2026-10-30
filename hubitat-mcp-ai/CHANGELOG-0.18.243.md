# v0.18.243 — complete evidence accounting and consistent causal explanation

## Failure reproduced

The 30 October 2026 11:09 original HomeBrain investigation returned six
Bathroom Light 1 device events (two issued OFF, two setLevel, two reported
levels) and four Bathroom Light 2 events (two issued OFF, one setLevel,
one reported level), but *no switch ON/OFF state* for either target. Shower
Light did return switch ON/OFF transitions. The original answer nonetheless
claimed all light events were setLevel, no OFF commands or states occurred,
and location mode changes or motion had definitively activated every light.
Its appended verified switch timeline did not repair that false prose.

## Bottom-up source evidence contract

- Build a **source-attested incident ledger** that retains separately typed
  issued `on/off/setLevel` commands, reported switch transitions and reported
  brightness levels, sorted by actual source timestamp. Preserve all target
  identities including named target devices with zero switch events.
- Publish a typed per-target coverage summary: number of issued commands,
  observed ON/OFF switch changes, level reports and any missing switch history
  despite commands. No fabricated switch transitions.
- When no target switch history is returned despite commands, the **original
  model**, not a host keyword router, receives a bounded evidence recovery
  suggestion to use independently authorised switch-only historical reads or
  incident-time app logs. No new MCP permissions and no writes.
- Use the original HomeBrain natural-language reasoning when supported.
  At the last request boundary, detect assertions incompatible with source
  receipts, including "no OFF commands" where app OFF commands are returned,
  false "all light events were setLevel" and activation certainty despite
  missing switch histories. Replace, do not append beneath, contradictory
  explanations with a single source-first explanation and incident ledger.
- Do not claim the Hue/Aqara bridges initiated an event merely because they
  reported it; later setLevel is not evidence it caused an earlier reported ON.
  Static Groovy code does not prove incident-time execution.
- Preserve the previously retired standalone Investigation V2 test UI/API
  removal, original MCP Main Ask and existing V2 evidence utility regressions.

## Verification

Replay exact 11:09 incomplete Bathroom event receipts and contradicted live
model response at the original HomeBrain terminal response boundary;
assert both Bathroom OFF apps (1568 and 1569), 07:12/07:15 issued level
commands, Shower ON/OFF reported transitions, and no invented 02:18/02:52
log-only transitions. Test unverified identity, read-only proof, evidence
coverage disclosure, prior complete switch-history behaviour and package smoke.
CI green is not the same as live Hubitat correctness; use Main Ask after
installing this version.
