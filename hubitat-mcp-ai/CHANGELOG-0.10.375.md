# 0.10.375

## Fixed

Follow-up debugging pass after 0.10.373/0.10.374's firmware work, done at
the user's request to keep testing for issues rather than stopping once
the button-loop bug was confirmed fixed live. Live-checking the real hub's
Hub Info device mid-update (as part of validating 0.10.374's status check)
surfaced a second, more serious gap while reading through the confirm-step
code path both of those releases route through.

`ConfirmedActionCoordinator.resume()` has always had a deterministic
completion report for Rule Machine writes (`confirmed_rule_report`) --
verified/failed rule creation is never left to the model to summarize.
Every *other* confirmed sensitive or destructive write, including the
`hub_update_firmware` call 0.10.373 just built a whole deterministic
propose path for, had no equivalent: after execution, `resume()`
unconditionally handed the raw tool result to the model and trusted its
free-form narration to correctly carry forward whether the call actually
succeeded, and any `warning` the hub returned. This session found that
exact class of trust unreliable repeatedly (the weather-routing bug, the
firmware-install button loop itself) -- there was no reason to expect it
to be reliable here, and the failure mode is worse: a genuinely failed
sensitive write narrated as a success.

The `hub_manage_destructive_ops` gateway (permanent device deletion, radio/
network resets, hub reboot/shutdown -- Hubitat's own tool description
calls these "irreversible or cause significant downtime") goes through
this exact same unguarded path today.

## Fix approach

Added `ConfirmedActionCoordinator.confirmed_firmware_report()`, the same
treatment `confirmed_rule_report` gives Rule Machine, specifically for
`hub_update_firmware`: deterministically reports failure (using whatever
`error`/`message`/`warning` field the result carries) or success (message
plus any `warning`, plus a pointer to the new "ask for update status"
check), and never reaches the model for this call at all. `tool_registry`
gained a public `HUB_UPDATE_FIRMWARE_TOOL` constant so the tool name
exists in exactly one place instead of being duplicated as a string
literal across `homebrain_agent.py`, `confirmation_policy.py`, and
`tool_registry.py` itself.

Added a second, narrower safety net, `confirmed_failure_report()`, for
every other confirmed action this coordinator has no tool-specific report
for -- most notably `hub_manage_destructive_ops`. There are no live
example payloads to build a full per-tool success report against safely
(unlike firmware, which was verified against the real hub this release),
so this deliberately does not try to replace the model's success
narration. It only intervenes when `ToolExecution.success` -- computed
generically by `ToolExecutor.succeeded()` from the raw result, independent
of any tool-specific schema -- is `False` for something in the confirmed
group. In that case it reports the failure deterministically and never
lets the model narrate it, closing the one-directional risk that actually
matters: an irreversible destructive write being reported to the user as
if it had succeeded when it had not.

## Validation

- `python -m pytest -q` -- 643 passed (5 new/changed:
  `test_confirmed_action_coordinator.py`'s
  `test_failed_destructive_op_is_reported_deterministically_not_by_model`
  proving a failed `hub_manage_destructive_ops` call is reported without
  ever invoking the chat callback; `test_homebrain_agent.py`'s two new
  `test_firmware_confirm_deterministically_reports_a_hub_side_failure` and
  `test_firmware_confirm_surfaces_a_hub_warning_alongside_success`; the
  existing firmware-confirm integration test and
  `test_confirmation_enforcement.py`'s base-orchestrator firmware test
  updated for the new deterministic confirm-step wording, both now also
  asserting zero model calls across the full propose-then-confirm flow).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.375
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: trigger a real firmware confirm and check the
  server log shows no `Ollama streamed round completed` line for that
  step (proving the model was never called); a destructive-ops failure is
  harder to safely reproduce live and was not attempted -- the unit test
  above is the coverage for that path until a real failure is naturally
  observed.
