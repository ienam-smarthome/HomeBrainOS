# v0.18.384 — native MCP device-read contract and honest failed lookups

## Real Q1 observation

The user submitted the **registered** frozen Q1 `status_named_dimmer` request on installed v0.18.383: `Read the current switch state and brightness of Livingroom Light 2.` The source receipt reported a **failed** targeted `hub_list_devices` call, then a failed `homebrain_resolve_device` call, with no switch/level facts. The natural answer correctly declined to invent values but the UI incorrectly displayed `outcome=success`. Runtime: **7.177s** overall, 4 free Gemma 4 31B rounds, 2 tool receipts. The API submitted-question hash was present, but actual model input / first attempt / deployed SHA remain unverified.

**Root cause verified in source, not upstream response text:** HomeBrain's shared list read plan and MCP normalizer used `detailed=true` and `offset=...`. The upstream `kingpanther13/Hubitat-local-MCP-server` `_listDevicesArgNames()` instead accepts `format` (`summary` or `detailed`) and `cursor`, rejecting unknown arguments **before** any hub inventory read. No raw upstream error from this user's run was retained, so this is a contract-backed explanation, not a direct error-code reproduction.

## General fix (not name-specific)

- Change the shared device projection plan and MCP boundary normalizer to the **actual upstream wire argument names**. Map internal legacy `detailed` to `format="detailed"` and `offset` to `cursor`. Remove the unsupported keys before any remote request, without broadening requested scope, labelFilter or authorization.
- Preserve the projected `attributes` versus `currentStates` state-field contract and fail closed if a non-empty source response omits the promised state shape.
- Add `device_resolution_source_failed` to the request's bounded diagnostics and classify such failures as **unresolved**, not `success`. A failed targeted read does **not** establish device absence.
- Do not mark failed local resolver tool receipts as evidence supporting live-state claims. Valid source results can still be used by normal natural-language reasoning; no deterministic status sentence is added.
- Synthetic regression tests include the upstream-style unknown-argument error, valid named dimmer state data, read failure outcome, privacy-safe tool receipt and multi-mode projection. No real device data are placed in fixtures.

## Outcome and limits

**Before (one user run):** source rejected, no current switch/level values, 7.177s, outcome wrongly green. **After:** changes tested offline; **installed live acceptance not yet measured**. The PR does not assert that a particular household device is currently ON/OFF or what its brightness is, and does not establish an accuracy or latency change. First-attempt Q1 and Q2 model-comparison aggregates remain **not measured**.

**Safety:** No Hubitat or Home Assistant calls during repository development; no device, rule, automation, or Internet-blocker changes. Existing runtime write authorization and model-led responses remain unchanged. Roll back the normalizer, counter/presentation and tests if incompatible upstream versions are demonstrated; do not mask invalid native arguments with additional retries. The Internet-blocker remains paused.

**Live acceptance (after installed release):** For a new read-only Q1 request with a frozen question that has not already been retried, compare exact prompt hash, transmitted native args, successful state source and public outcome. Repeating Livingroom Light 2 for *regression acceptance* is valid but is **not a new independent first-attempt benchmark case**.
