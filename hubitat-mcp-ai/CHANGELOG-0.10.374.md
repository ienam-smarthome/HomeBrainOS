# 0.10.374

## Added

Follow-up to 0.10.373's firmware-install fast path. Live-testing that fix
worked correctly (deterministic confirmation queue, real `hub_update_firmware`
call on "confirm"), but surfaced a related gap: once an update starts, the
only way to check on it was the hub's own native Settings > Check for
Updates page, which shows a live download percentage the assistant has no
access to at all -- the confirm-step message even says "you can check the
progress by asking me for the update status", but nothing recognised that
phrasing yet.

Investigated what Hubitat's Hub Info driver actually exposes during an
active download by reading the live device's attributes mid-update: the
`hubUpdateStatus` attribute stayed at `"Update Available"` throughout,
never surfacing a percentage or a `"Downloading"`/`"Installing"` state.
That means a true progress percentage isn't obtainable through this
integration path at all -- only whether `installed_firmware` has caught up
with `available_firmware` yet. The fix below reports exactly that, and
says so explicitly rather than implying more precision than the data
supports.

## Fix approach

Added `parse_firmware_status_intent()` to `request_classification.py`,
next to `parse_firmware_install_intent()` (kept in the same module despite
being read-only, since it's firmware-domain-specific rather than a
device-attribute read, and pairs directly with the write-intent parser it
mirrors). Narrow `fullmatch` over update-status/progress phrasing
("update status", "how's the firmware update going", "is the update
done") -- deliberately excludes generic firmware questions like "check
firmware" (already handled fine by the existing snapshot flow) and install
directives (stay on `parse_firmware_install_intent`), since this is a
distinct read-only trigger from both.

Added `UnifiedMCPAgent._firmware_status_outcome()` in `homebrain_agent.py`,
wired in ahead of the install-intent check. Reads the same firmware
snapshot the install flow uses and reports one of three states without any
model round: "up to date" (covers both "never pending" and "just finished"
-- `update_available` can't distinguish the two, so the wording is chosen
to read correctly either way), "still in progress" (installed still trails
available, with an explicit note that no live percentage is available and
a pointer to the hub's own UI for that), or a read failure passthrough.

## Validation

- `python -m pytest -q` -- 640 passed (4 new:
  `test_live_soak_correctness.py`'s
  `test_firmware_status_intent_matches_only_progress_questions` covering
  the regex's positive/negative matches; `test_homebrain_agent.py`
  full-agent integration cases proving a status question mid-update
  answers deterministically with no model round and no percentage claim,
  the same question reports "up to date" once versions converge, and a
  status question never triggers the install-confirmation path).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.374
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: ask "how's the update going" or "update status"
  while a real install is in progress and confirm the response reports
  "still in progress" with `"model": null`; ask again once the hub finishes
  and reboots and confirm it reports "up to date" with the new version
  number.
