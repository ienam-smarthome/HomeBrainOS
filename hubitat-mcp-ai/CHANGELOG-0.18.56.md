# HomeBrainOS v0.18.56 — Bounded Rule Machine 5.x dependency references

## Observed limitation
v0.18.55 successfully reached the comprehensive audit and read six current app pages, but identified zero action/trigger fields. A targeted read of Rule Machine 5.1 rules later showed the upstream source may expose indexed keys such as `onOffSwitch.3`, `tCapab33`, `startingA22`, `endingA22` and `selectHoursC33` only through the separate `settings` object. The current generic probe deliberately requested `includeSettings:false` and never interpreted this object.

## Implementation
- Add `rm_settings_dependency.py`: a strict RM 5.x app-type gate and finite indexed-key-family interpreter. Return only counts and numeric device **references**. No values, names, arbitrary setting keys, location, credentials or URL content are emitted. No raw settings object retained.
- Keep six normal `includeSettings:false` configuration reads and the original two-concurrent six-second combined budget. Only after those reads, at most two exact verified RM apps without typed action evidence receive bounded `includeSettings:true` read-only reads under the same budget.
- Discover actual device references through the recognised `onOffSwitch.<index>` map shape. References are NOT asserted to be targets, triggering subscriptions, action commands or execution. Any shared reference is explicitly weak; it does not create `typedActionDeviceOverlaps`.
- Use `hub_list_device_dependents` with **deviceId** (not appId) for at most two discovered devices; if the result has a verifiable `appsUsing` collection, corroborate selected installed app references. Do not infer action direction.
- Give known RM-type lighting candidates priority over lower-numbered unrelated lighting parent apps, while preserving the disabled-app and heartbeat categories. Never hardcode real app IDs.
- Add receipts for bounded RM shape reads and device-oriented dependents lookups. Explicitly distinguish configuration page verified, indexed reference interpreted, and history/callback not verified.
- Regression tests cover role uncertainty, wrong IDs, app-type gating, sensitive settings filtering, bounded concurrency, successful/failed dependents, no writes, and zero budget.

## Limits
The indexed settings key family alone cannot decode complete Rule Machine trigger/action semantics. The parser must not claim action target, historical execution, schedule callback ownership or conflicts without independent typed action/compiled-rule evidence. Even read-only Hubitat page retrieval may perform upstream rendering/recompilation, so follow-ups are strictly bounded.
Live add-on verification is required after merge; CI success is not live confirmation.
