# Hubitat MCP AI 0.10.356

## Fixed

- **A compound request mixing a routine device action with an unrelated
  second action got folded into a single malformed tool call instead of
  two separate ones.** Live test: `"turn off toilet light and restart the
  hub"` was sent to `homebrain_control_devices` as one call with
  `device_names: ["toilet light and restart the hub"]` -- the model treated
  the whole phrase, including "and restart the hub," as part of the device
  name list. The deterministic target resolver correctly refused to guess
  (fail-closed, exactly as designed: "No candidate was similar enough...")
  so nothing wrong actually executed, but the request should have succeeded
  as two independent actions (turn off the light, restart the hub) rather
  than failing as one unresolved one.

  This is a different failure than 0.10.355's mixed-confirmation-round bug:
  that bug was about the *host* dropping one of two tool calls the model
  had already correctly issued in the same round. This bug is upstream of
  that -- the model never issued a second tool call at all, because the
  system prompt's "call `homebrain_control_devices` once" instruction was
  ambiguous about what "once" scoped over.

  Fixed by clarifying the `ROUTINE DEVICE CONTROL` prompt section in
  `agent_prompt_policy.py`: `device_names` may only contain device name
  fragments that share the same command, and a second distinct action in
  the same sentence (a different command, a different gateway's action, or
  wording like "and restart the hub" / "and lock the door" / "and arm the
  alarm") must be issued as its own separate tool call in the same round.

## Context

This is a prompt-level fix, not a deterministic code-path fix like most of
this session's other changes -- it steers the model's behavior rather than
mechanically enforcing it, so it cannot carry the same certainty as, say,
the regex-grammar fixes in 0.10.354. The deterministic safety net (refusing
to guess an unresolved device) already ensured the failure mode was safe
rather than silently wrong; this change is aimed at making the request
actually succeed, not just fail safely. If this exact phrasing (or a
similar one) still misfires after this change, the next step would be a
deterministic pre-split of compound "X and Y" requests before the model is
invoked -- a larger change deliberately not attempted here without first
seeing whether the prompt clarification resolves it.

## Validation

- `python -m pytest -q` -- 572 passed, including a new regression test
  (`test_control_prompt_forbids_folding_a_second_action_into_device_names`)
  asserting the new prompt guidance text is present.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.356.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Not yet re-verified live -- pending the user re-running the same failing
  phrase after this update is deployed.
