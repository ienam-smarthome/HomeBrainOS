# HomeBrainOS v2 alpha.78 — source-attested native one-off Rule Machine + opt-in cleanup

**13 November 2026 — development-only. No live rule was created, paused or deleted by this repository change.**

## Original regression

The private alpha.77 first-answer capture for an unqualified single-time request displayed an activated **Visual Rules Builder 2.0 `timeOfDay=1850`** rule. That trigger is **daily**, not once. The selected `turnOn` action targeted an Internet-control switch whose previous source values were `switch=on` and `internetAccess=allowed`. The original response confirmed storage/activation, not any blocking outcome. A photo separately showed another same-named VRB child, not an independently validated second currently active rule.

The original HomeBrain V1 scheduling workflow was real. Merged [#692](https://github.com/ienam-smarthome/HomeBrainOS/pull/692) created relative one-time schedules, [#697](https://github.com/ienam-smarthome/HomeBrainOS/pull/697) fixed hub-local timing, and [#698](https://github.com/ienam-smarthome/HomeBrainOS/pull/698) established cleanup of expired owned rules (originally **01:00**). The later code prefixed newly owned names `HB one-shot |`. [#1469](https://github.com/ienam-smarthome/HomeBrainOS/pull/1469) **intentionally removed** the V1 cleanup scheduler/service. Neither it nor the old Rule Machine request shape was ported to V2. Older V1 `hub_set_rule({name,addTrigger,addAction})` is incompatible with current native MCP `hub_set_rule({operation:"create",args:{parent_id,name,changes}})`.

## Model-led restoration with explicit denial-only limits

1. The MODEL still discovers and selects the native tool, actual actuator and requested time. It may prefer a verified device-owned timer for a relative delay; a genuine one-off fixed-time action may use **Rule Machine**. No device, command or rule is hardcoded, and no proxy/virtual helper is created.
2. A **denial-only temporal check** prevents a model-selected VRB rule for a one-off request, because VRB's presented `timeOfDay` trigger repeats. Bare `at HH:mm` without a recurrence marker is treated conservatively as a one-off for this check; explicit `daily/every day` remains recurring. Short assent carries the prior schedule only for denial, not for permission. The check does **not** grant write authority.
3. For a one-off Rule Machine write the proposed native `hub_set_rule(operation=create)` must contain **one typed `Certain Time (and optional date)` trigger**, with both `date#=true` and `atDate#` plus an offset-aware `atTime#`. The label must match that exact date and time, prefixed `HB one-shot |`. One native Switch action is allowed in this conservative initial contract; the exact target and selected `on/off` command must have been read from the current hub, and the native Rule Machine parent ID must have been source-attested with typed `appType.namespace=hubitat, appType.name=Rule Machine`. A past or imminent deadline is rejected. This shape follows the post-5.1.6 native-document contract; server schema/permission/backup/validation and the alpha.76 operation-specific UI approval remain mandatory.
4. The model must still verify that an advertised Switch command produces the requested **real-world effect**. A stored or activated rule does not attest the trigger or downstream effect. This release does not assert the installed hub exposes typed parent identity or will accept the native dated create: absent necessary current evidence the writer **fails closed**, rather than guessing or silently installing a daily rule.
5. A failed or ambiguous native create must not be blindly retried; read the native inventory/health first and reconcile exact identity.

## Owned cleanup restored as a separate opt-in

The V2 add-on gains:
```yaml
one_off_cleanup_enabled: false
one_off_cleanup_dry_run: true
one_off_cleanup_time: "07:00"
one_off_cleanup_timezone: "Europe/London"
one_off_cleanup_grace_minutes: 15
```
Defaults protect existing rules. To **observe** candidates, enable the scheduler while leaving dry-run true, restart the add-on and review `/api/status` → `one_off_cleanup` after the next scheduled run. To enable automatic soft deletion, the owner must **separately** set `one_off_cleanup_dry_run=false`, with a recent hub backup and MCP permission. No automatic deletion is enabled merely by updating.

The cleanup only considers a rule whose name is an exact **`HB one-shot | ... (One-time YYYY-MM-DD HH:MM)`** match and whose date has passed its grace period in the configured hub-local timezone. It reads the authoritative installed rule list, re-reads the native Rule Machine document for actual typed `settings`, independently reads the installed child's app type/label through `hub_get_app_config`, requires exact typed `hubitat/Rule-5.1`, the named calendar date, clock time and Switch action, and only then submits `hub_delete_native_app(force=false, confirm=true)` through the installed MCP server. Malformed or insufficient reads, future dates, wrong engines, suffix-only older V1 rules and unrelated Visual Rules fail closed. A write timeout/unknown result is durably held for manual review, never blindly retried.

The scheduler operates independently of an Ask request; an enabled cleanup is a separately configured owner policy, **not** approval obtained from chat text. Persistent state records the latest date/run and uncertain deletions. The cleanup is a best-effort morning maintenance task, not a promise of deletion if HA/HomeBrain or the hub is offline. On restart, no retroactive dangerous bulk purge runs.

## Acceptance boundary

Synthetic tests verify no one-off-to-daily VRB creation, native dated typed single Switch contract, exact current source parent/target reads, expired-date refusal, spoken/numeric delays and chat assent, configured dry-run, narrow matching, native read-before-delete, and durable uncertainty hold.

**Outstanding live acceptance:** Verify parent app typed identity and the installed native one-off create schema via read-only MCP sources. Ask HomeBrain one fresh natural-language one-time action and inspect PRIVATE original MCP receipts and UI approval. Confirm the output is one dated native Rule Machine rule (or a truthful refusal), then verify its actual trigger/time/command outcome on Hubitat. Only after proving that path should the owner opt in to **real** morning cleanup. Do not assume a passing CI means hub execution worked. Leave current rules 4303/4304 and unrelated V1 rules untouched by this repository work.

**Scope:** No V1, external monitor, router, Hubitat driver, or existing rule modifications. Gate B remains the broader cross-domain reasoning programme.
