# 0.10.368

## Fixed

Live retest of 0.10.367 (the prompt-guidance tightening for whole-home
power queries) surfaced two new, deterministic bugs in the same query flow
against the real Octopus Energy meter device (Hubitat device 7434):

1. **Empty answer after exhausting the tool-round budget.** "current power"
   sometimes returned the literal placeholder "The MCP request completed
   without a written answer." after 6 tool-calling rounds and one forced
   final-answer call, even though the tool responses along the way had
   already revealed the correct attribute names (`value`/`valueStr`).
   Root cause: `UnifiedMCPAgent.max_tool_rounds` was hardcoded to 6 with no
   config path. A meter device that requires several failed attribute-name
   guesses and an invalid-parameter retry before landing on the right
   attribute name can burn through 6 rounds before ever reaching an
   answer. Fixed by raising the default to 9 and exposing it as a new
   add-on option, `unified_mcp_max_tool_rounds` (default 9), wired through
   `app.py` the same way `unified_mcp_tool_limit` already is.

2. **False "returning a null value" claim.** A separate run of the same
   query reached `hub_get_device_attribute(deviceId=7434, attribute=value)`,
   got back `value: null` (this device's `value` attribute is frequently
   null even when it has a live reading -- the real number lives in
   `valueStr`, e.g. "231 W"), and the model reported this as an outright
   failure instead of retrying with `valueStr`. Root cause: the existing
   `value`/`valueStr` fallback (`DeviceQueryService._attribute_value()`,
   added in 0.10.366) only covers the local `homebrain_*` fast path used
   for named-device lookups. A bare "current power" query with no device
   name never matches that fast path's regexes, so it goes through the
   full LLM tool-calling loop and the raw external `hub_get_device_attribute`
   gateway tool instead, which has no such fallback and was relying purely
   on prose guidance (0.10.367) for the model to retry -- unreliable, as
   observed live.

## Fix approach (deterministic, not prompt-only)

Rather than tightening the prompt further -- which the 0.10.367 changelog
already flagged as merely probabilistic -- this release fixes the second
bug at the code level. `ToolExecutor.execute()` (`tool_executor.py`) now
recognises the specific shape of a null generic-value read
(`hub_get_device_attribute` called with `attribute="value"`, response has
`value: null` and no `valueStr`) and transparently issues one automatic
follow-up call for `attribute="valueStr"` on the same device, merging the
result in before it's ever shown to the model. This mirrors the existing
`allow_generic_value_fallback` logic in `device_query_service.py`, applied
at the one remaining code path (the raw hub-gateway tool) that didn't have
it. The model now sees `valueStr` already populated in the same tool
response and never has to guess, retry, or rely on the prompt hint to get
there -- and it costs one extra fast tool round trip (already observed at
600-800ms) only in the rare case where `value` actually comes back null,
never on devices that already report a real number.

The `max_tool_rounds` fix (bug 1) is a plain, deterministic config/default
change with no probabilistic component.

## Validation

- `python -m pytest tests/ -q` -- 616 passed (6 new: 4 in
  `test_tool_executor.py` covering the automatic valueStr backfill --
  triggers on null value, skipped when value is already present, skipped
  for non-`value` attribute reads, and fails gracefully if the follow-up
  call itself errors -- plus 2 in `test_orchestrator_max_tool_rounds.py`
  covering the new default and its configurability/floor). One existing
  test (`test_confirmation_enforcement.py`) was updated to supply 9 canned
  responses instead of 6, since it deliberately exhausts the tool-round
  budget and was calibrated to the previous default.
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py`
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
