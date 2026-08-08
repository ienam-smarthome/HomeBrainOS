# 0.10.373

## Fixed

Clicking the WebUI's "Update hub firmware" button appeared to loop forever.
The button just resubmits the fixed text "Install the available Hubitat
firmware update"; the system prompt told the model to "call
`homebrain_hub_info_snapshot`... [then] only call `hub_update_firmware`
after the snapshot reports `update_available=true` and the host
confirmation gate approves it" -- trusting it to chain a second tool call
across tool-selection rounds. Live testing showed the model never made that
second call, even for the exact button text: every request only ever
called the read-only snapshot and narrated a summary. Because the
confirmation gate only engages once the sensitive `hub_update_firmware`
call is actually attempted, it never fired, so the button's resubmission
produced the same non-mutating response every time -- an infinite loop from
the user's perspective. This is the same failure class 0.10.370 fixed for
weather-vs-indoor routing: prompt-only steering asking the model to make a
specific tool-call decision is not reliable enough for something the host
needs to guarantee.

## Fix approach

Added `parse_firmware_install_intent()` to `request_classification.py` (not
`contextual_read_fast_path.py` -- that module is for read fast paths, this
is a write-intent trigger) as a narrow `fullmatch` over the WebUI button's
own text and reasonable variants ("install firmware", "update hub
firmware", "upgrade the hub firmware", etc.), deliberately excluding
read-only phrasing like "check firmware" or "is there a firmware update"
since false positives matter far more for a sensitive-write trigger than
they do elsewhere in the fast-path system.

Added `UnifiedMCPAgent._firmware_install_outcome()` in `homebrain_agent.py`,
wired in right before the existing control-argument routing. It reads
firmware state itself via the existing `_hub_info_snapshot({"scope":
"firmware"})` path and records the same evidence a normal snapshot call
would. If no update is available, it reports that directly and stops --
no confirmation is queued and `hub_update_firmware` is never referenced.
If an update *is* available, it builds the same kind of tool-call payload
the model would have produced for `hub_update_firmware`, runs it through
the existing `ConfirmationPolicy.decide()` gate, and -- for the normal
QUEUE outcome -- calls `self.confirmations.queue()` with a synthetic
assistant tool-call message so the pending confirmation has something
sensible to show in chat history. This does not bypass the safety gate:
`ConfirmedActionCoordinator.resume()` executes `pending.actions` directly
rather than re-parsing the stored assistant message, so the actual
`hub_update_firmware` call still only runs once the user replies
"confirm", exactly as it would if the model itself had proposed the call.

Because this route queues its own confirmation before returning, and the
generic `DirectOutcomeContext.run()` wrapper used by every other
deterministic fast path does not check confirmation state, the outcome's
`confirmation_required`/`confirmation_count` fields are set manually after
`_direct_outcome()` returns -- mirroring the computation the base
orchestrator's `process_user_request_result` normally does automatically
for model-driven requests, which these deterministic fast paths bypass.

Per the explicit follow-up request to check for other routes with the same
bug shape: searched `agent_prompt_policy.py` for other "only call X after Y
reports Z" chaining instructions and `webui.py` for other buttons that
resubmit fixed text expecting a sensitive follow-up call. The firmware
line was the only prompt instruction of this kind, and the "Update hub
firmware" button was the only special-purpose button beyond the generic
"Confirm action" button. No other route in the codebase currently asks the
model to autonomously chain into a sensitive tool call across rounds, so
no other fix was needed this release.

## Validation

- `python -m pytest -q` -- 636 passed (4 new:
  `test_live_soak_correctness.py`'s
  `test_firmware_install_intent_matches_only_genuine_install_directives`
  covering the regex's positive/negative matches; `test_homebrain_agent.py`
  full-agent integration cases proving an install directive queues a
  confirmation and resumes to a real `hub_update_firmware` call, an install
  directive with no update available reports that without queuing
  anything, and a read-only firmware question never triggers install
  intent at all).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.373
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: click "Update hub firmware" (or type "install
  firmware") against the real WebUI with an update actually available, and
  confirm the response shows `confirmation_required: true` with the
  firmware confirmation wording and `"model": null` (no Ollama round);
  reply "confirm" and check the server log for an actual
  `hub_update_firmware` call; re-run with no update available and confirm
  it reports up to date without offering to confirm anything.
