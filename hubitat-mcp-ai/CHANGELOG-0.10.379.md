# 0.10.379

## Why this release

The previous three releases (0.10.377/0.10.378) fixed the live "block the
tv" bug and its immediate aftershocks one reported phrasing at a time.
That reactive, one-bug-report-at-a-time approach is not sustainable on
its own -- a hand-written regex parser can only ever recognise the
phrasings someone thought to test. This release is a deliberate hardening
pass instead: it pulls the complete live device inventory (89 devices)
straight from the real hub, uses it to find every other naming collision
of the same shape as "TV" vs. "Block Google-TV-Streamer", and -- most
importantly -- closes the gap for phrasing nobody has tested yet by
teaching the model's own fallback path to resolve devices safely,
instead of relying solely on an ever-growing list of regexes.

## Found and fixed

**A second and third real naming collision in the live inventory.**
Pulling the full 89-device list surfaced two more devices whose command
list makes them indistinguishable by a short name from an unrelated
device: "Block PC-NucBox-M6Ultra" (the only device that can block
internet for that machine) shares the word "PC" with an unrelated MQTT
outlet literally labelled "Bedroom3 PC (MQTT)", and "Block
CAM-Camera-G100-42EA"/"...-7B37" share "CAM" with "HallwayCAM (MQTT)".
Verified against the real fixtures: the existing capability-scoping fix
from 0.10.378 already handles both correctly (capability filtering
excludes the incapable MQTT devices before name matching ever runs), so
this release adds regression tests locking that in rather than needing a
new code fix -- but it would have gone unverified without pulling the
real inventory and checking it explicitly, which is the actual point of
this pass.

**The model's own fallback path had no way to avoid the original
mistake for phrasing the deterministic parser doesn't recognise.**
This is the structural fix. Previously, `homebrain_resolve_device` (the
only device-lookup tool exposed to the model) accepted just a device
name -- no way to ask for a device that specifically supports a given
command. And the system prompt had zero guidance about "block internet
access" phrasing outside the Rule Machine authoring section, so a
phrasing that slipped past the regex fell into the same tool-selection
loop that originally turned the TV off. Two changes close this:
- `device_resolver_tool()`'s schema now accepts an optional
  `required_command` parameter, which the existing
  `DeviceQueryService.resolve_device()` capability scoping (added in
  0.10.378) already honours end-to-end with no further plumbing needed.
- The system prompt gained an explicit INTERNET ACCESS CONTROL section:
  block/disable/restrict/allow/enable/unblock/restore internet-access
  wording is never a power on/off request, `homebrain_control_devices`
  rejects blockInternet/allowInternet outright (it only accepts
  on/off/toggle) so it must never be used for this, and the model must
  always resolve via `homebrain_resolve_device` with `required_command`
  set before dispatching the verified command through
  `hub_call_device_command`. This does not guarantee the model always
  obeys it, but it closes the gap for genuinely novel phrasing that no
  deterministic parser was ever going to anticipate -- the fast,
  deterministic path remains the primary defense for the phrasings it
  does cover.

**Deterministic vocabulary gaps.** "restrict" is an unambiguous
internet-access synonym for "block" and is now accepted the same way
"disable" already was, in both the immediate parser and
`RuleAuthoringService`. "unblock"/"restore" are NOT safe to accept as
loosely -- both words are heavily overloaded elsewhere in the codebase
(a hub backup can be "restored") -- so they only count as
internet-access requests when "internet"/"access" is stated explicitly
("restore internet access for the tv", not a bare "restore the tv").
Verified "restore the backup" and "restore default settings" are never
hijacked by this parser.

## Validation

- `python -m pytest -q` -- 669 passed (7 new: resolver-tool schema
  exposes `required_command`; all five real internet-blockable devices
  from the live inventory resolve by their distinguishing word; the "PC"
  and "CAM" collisions found in the live inventory are handled correctly;
  "cam" alone is honestly reported as ambiguous between the two real
  cameras, not silently guessed; the new "restrict"/explicit
  "unblock"/"restore" vocabulary is recognised; a bare "restore the
  backup" is never hijacked; the system prompt carries the new
  INTERNET ACCESS CONTROL guidance).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.379
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live device inventory pulled directly from the real hub via
  `hub_list_devices` (89 devices) and archived as
  `tests/fixtures/live_devices_2026-08-08.json` for this and future
  hardening passes, rather than relying on hand-written fixtures alone.
