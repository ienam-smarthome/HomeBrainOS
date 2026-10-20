# HomeBrainOS v0.18.47 — Reconcile Internet driver capability guidance

## Live observation
On v0.18.46, a scoped read-only Hubitat check verified TV power plug 4221 (Multimedia; off; 0 W) and Internet-room Google TV access control 6923 (off). The latter actually advertises `on`, `off`, `blockInternet`, `allowInternet`, `addTime` and `resetUsage`. The model completed the request, but used 6 Gemma rounds in ~31 seconds and attempted 1 write, safely blocked by the read-only authorization gate.

## Changes
- Fix model-visible resolver guidance that previously treated `blockInternet` / `allowInternet` as nonexistent and told the model never to consider them. The commands do appear on some real devices, so the guidance must not contradict the authoritative device metadata.
- Preserve HomeBrain's established deterministic Internet-room control: `switch=off` means blocked, `switch=on` means allowed. Ordinary immediate/scheduled actions **continue** to compile to real `off` / `on` commands and verify the switch attribute.
- Differentiate semantic intention, real device-advertised capabilities and **unverified** driver-specific command behavior. The mere presence of `addTime` / `resetUsage` does not establish cumulative time accounting, reset triggers, parameter semantics or durable state.
- Explicitly instruct the model-visible resolver not to call control commands for read-only investigations.
- Add tests for capability-neutral guidance and no blanket denial of advertised methods.

## Still unverified
- TV smart plug 4221 was off at 0 W: active-viewing and standby power levels were **not** sampled, so no watt threshold can yet be justified.
- No tests of the live effects of `blockInternet`, `allowInternet`, `addTime`, `resetUsage`, or Internet reachability were performed.
- The recorded blocked model-proposed write did **not** execute. Further agent tool-selection optimization is separate work; this change does not guarantee no future model write proposals.
- The cumulative 60-minute TV allowance has **not** been created.

All changes are limited to guidance, code comments, tests and release metadata. No Hubitat devices, rules, schedules or settings are changed. Merge only after all three CI workflows pass.
