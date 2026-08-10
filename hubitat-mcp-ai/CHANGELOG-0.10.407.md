# 0.10.407

## Why this release

Ships 8 of the 9 Tier 2 (medium confidence/severity) findings from the
2026-08-10 full code review, all reproduced directly before fixing. One
finding (#5, a weaker success check on confirmed firmware reports) is
deliberately deferred -- see "Deferred" below.

## Fixed

**A duplicate tool-call signature could silently drop a later, genuinely
new call in the same round.** `mcp_agent_orchestrator.py`'s
`completed_calls` duplicate-signature guard returned a final answer the
instant it saw a repeated call signature, abandoning any remaining calls in
that same tool-calling round -- including a write -- with no tool-role reply
and no evidence receipt, while the model's own narration could still
confidently claim the whole round succeeded. The duplicate is still never
re-executed (avoiding a doubled real-world side effect), but a tool-role
reply is now appended for it and the rest of the round keeps executing; the
agentic loop still ends with a final answer once the round finishes,
preserving the original protection against a model repeating itself
forever.

**`ToolExecutor.succeeded()` was an independent third copy of the strict
`is False` success check**, alongside `mcp_client.tool_succeeded()` (fixed
in 0.10.406) and the two call sites already fixed in
`device_history_service.py`. This one gates `ToolExecution.success`
directly, which `confirmed_action_coordinator.py` and every other consumer
of a `ToolExecution` treats as authoritative -- a `{"success": "false"}`
response would have passed straight through as success here too. Now
delegates to the shared helper.

**Duplicate-rule protection silently skipped whenever `hub_read_rules`
happened to be truncated out of a turn's tool catalog.**
`rule_authoring_service.py`'s `_existing_names()` duplicate check was gated
on `can_read_rules`, which was driven by whether `hub_read_rules` survived
the per-request tool-catalog build (capped at `tool_limit`, default 48) --
an incidental, discovery-dependent signal, not a guarantee the gateway
doesn't exist. `_existing_names()` calls `hub_read_rules` directly via the
MCP client, not through the model's declared-tool schema, so it never
needed that signal in the first place, and it already fails closed to an
empty set if the call genuinely errors. The gate is removed (default
changed to `True`); repeated identical schedule requests are now reliably
told "already exists" instead of silently creating additional duplicate
Rule Machine rules.

**`grounding_policy.py`'s `logs_checked` overwrote instead of latching.**
`self.logs_checked = bool(success)` on every log-tool call meant a later
failed or duplicate log fetch in the same request could un-satisfy log
evidence a prior call in the same turn had already recorded successfully,
producing a spurious retry or, in the worst case, a false log refusal
despite genuinely available evidence. Now latches (`logs_checked = True`
stays `True` for the life of the request), matching the one-way retry
latches already used elsewhere on this same policy object.

**`capability_grounding.py`'s denial-detection regex had two gaps.** (a)
The "does not support/expose/advertise" pattern had no subject anchor, so
it also matched ordinary factual statements about a *device's* hardware
limits ("The dimmer does not support color temperature."), which could turn
an already-correct, grounded answer into a false rejection cycle. Now
anchored to the assistant/system/Hubitat as the subject, matching the
existing pattern for "cannot"/"am unable to". (b) The patterns required
spelled-out "do not"/"am unable to" and missed contractions -- "I don't
have the ability to control locks." bypassed denial detection entirely.
Contractions are now recognised.

**`request_classification.requests_mutation()` missed polite modal-verb
phrasing not paired with "please".** "can you lock the front door" and
"would you set the thermostat to 68" both returned `False`; only imperative
or "please"-suffixed phrasing was recognised. This gates whether the
identity-manifest grounding context gets injected for a legitimately
mutating request -- the same phrasing-coverage gap already fixed once for
"please".

**`tool_registry.py`'s `_DESTRUCTIVE_ACTIONS` set had two entries that
could never match.** `"factory_reset"` and `"reset_database"` are stored as
single multi-word strings, but the classification loop only ever checked
single-word tokens split on `_` before intersecting with this set, so those
two entries were dead code. Now also checks the un-split, already-
normalised operation string directly. Severity-labeling/audit-wording only
-- `confirmation_policy.py` already required confirmation for
`SENSITIVE_WRITE` and `DESTRUCTIVE_WRITE` identically, so this never
affected whether confirmation was required.

**Home-snapshot's "Attention needed" section hardcoded "offline or
unavailable" for every alert, even non-connectivity ones.**
`device_query_service.py` merges two different alert sources into one
bucket: a genuine connectivity signal (`healthStatus`/`networkStatus`/`rtt`)
and the device's raw `hubAlerts` text (which can carry battery, tamper, or
firmware warnings unrelated to connectivity). Every entry rendered with the
same hardcoded wording regardless of source. Each alert now carries a
`source` tag (`connectivity` or `hub_alert`) and renders with its own
reported status text, e.g. "Front Door Lock (low battery)" instead of
"Front Door Lock (offline or unavailable)".

**`agent_prompt_policy.py` embedded raw device attribute values into the
system prompt with no control-character stripping.** Device *labels* were
already rendered via `repr()` (escaping embedded newlines/quotes), but
attribute values used a bare `str(value)` -- a compromised or maliciously-
renamed device driver could embed a newline in its own reported attribute
value to make it look like a new prompt line (e.g. fake "SYSTEM:"
instructions). Both device-manifest attribute values and app-manifest
status fields now strip embedded control characters before rendering.

## Deferred

**Finding #5: `confirmed_action_coordinator.confirmed_firmware_report()`
uses a weaker success check than the sibling rule-write path**, and its own
docstring claims parity with that stricter check that the code doesn't
actually implement. Investigating this surfaced and fixed the
`ToolExecutor.succeeded()` gap above, which already closes the concrete,
verifiable part of this finding (a `{"success": "false"}` string flag now
correctly fails `execution.success`, which this report already checks).
The remaining gap -- a response that omits a `success` field entirely still
reads as success -- could not be safely verified: `hub_update_firmware` is
a real, irreversible, hub-rebooting action with no live-verifiable response
shape available in this environment, unlike Rule Machine (verified) or the
other findings in this release. Tightening the check to require an
explicit `success: true`, if the real response ever omits that field on a
genuine success, would report a successful firmware install as failed --
worse than the current gap. Left as-is pending a live-observed response
shape.

## Validation

- `python -m pytest -q` -- 801 passed (9 new test files/cases across the
  fixes above: `test_duplicate_call_signature_guard.py`,
  `test_tool_succeeded_consistency.py` (ToolExecutor case),
  `test_rule_authoring_service.py`, `test_grounding_policy.py`,
  `test_capability_grounding.py`, `test_request_classification_polite_modal.py`
  (new file), `test_tool_effect_registry.py`,
  `test_live_home_snapshot_presenter.py` + `test_device_query_service.py`,
  `test_agent_prompt_policy_manifest.py`). The duplicate-call-signature
  regression test was confirmed to genuinely fail against the pre-fix code
  before being included.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.407
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
