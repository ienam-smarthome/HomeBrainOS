# HomeBrainOS v0.18.73 — Typed partial installed-rule evidence

## Live comparison motivating this work

Version 0.18.72 correctly classified the 4246 vs 4019 investigation as a read. It also prevented claims unsupported by current typed receipts, but often returned a nearly empty report even when actual app pages and settings were available. Independent analysis showed indexed Rule Machine setting keys such as `delayMinute.3`, `cancelAct.3`, `onOffSwitch.5` and `onOff.5`, alongside custom controller `inactiveAction`.

## Improvements

- For targeted existing-rule audits, prefetch native health and local-variable evidence even when the prompt is too short to activate the older deep-rule heuristic.
- Perform a bounded, ID-verified `hub_get_app_config(includeSettings=true)` read for up to three explicitly named installed app IDs when the read-only apps gateway exists.
- Publish only allowlisted boolean, numeric and device-ID setting fragments in a privacy-safe `typed_existing_rule_partial_settings` receipt. Source maps may contain private labels, credentials and URLs; these are never exposed through this projection.
- Include verified partial field values in a conservative host-built report. Do **not** treat values as a validated order of executable actions, full trigger/condition logic or proof of runtime command execution.
- Retain `stored_logic=checked-unverified` / `evidenceComplete=false` until an independent complete Rule Machine typed action-tree/export is available.
- Unit tests cover typed config values, source IDs, redaction, unsupported values, truncation, read-only calls and completion boundary.

## Verification limits

This is not yet a certified full Rule Machine 5.1 action extractor or full app 4019 implementation/source review. Actual persistence key availability varies by device/app and firmware. A time field (e.g. `delayMinute.3=10`) proves only that persisted key's value, **not** that a specific runtime delay executed. We did not touch live Hubitat devices, rules or schedules.
