# 0.10.376

## Fixed

Full-codebase debugging pass at the user's request, done after confirming
the firmware work was solid live. Audited the confirmation lifecycle,
every deterministic fast-path regex, tool-effect classification, and
device control/rule verification for the same classes of bug already
found and fixed this session (unreliable model narration standing in for
a code-level guarantee, unverified writes, regex gaps). Two real bugs
were confirmed and fixed; several other findings are documented below as
known gaps, deliberately left unfixed this round (see "Found, not fixed
this round").

### 1. A stale sensitive-action confirmation could be silently resumed by an unrelated later message

Every deterministic fast path in `homebrain_agent.py` (including all the
ones added this session -- firmware install/status, bare attribute, etc.)
returns straight out of `operation()` without ever reaching the base
orchestrator's `ConfirmationStore.consume()`, which is the only place a
pending confirmation actually gets consumed or cancelled. Concretely:

1. User asks to install firmware -> a confirmation is queued.
2. Before confirming, the user asks something completely unrelated that a
   fast path handles directly (e.g. "turn off the kitchen light") -- the
   firmware confirmation is left sitting there, untouched, because that
   fast path never touches the confirmation store.
3. Later, the user says "yes" to something else entirely (or just as a
   filler word) -- this doesn't match any fast path, so it finally reaches
   the base confirmation-consume logic, which finds the *original,
   long-forgotten firmware confirmation* still pending and resumes it.

The same gap meant a fast path that queues its own confirmation (like
`_firmware_install_outcome`) could silently overwrite a still-pending
confirmation from an earlier, different request, with no notice to the
user about what got discarded.

### 2. `toggle` device commands were never state-verified, unlike `on`/`off`

`DeviceControlService` only attaches a `waitFor` block (and only computes
`verified`) for `command in {"on", "off"}` -- `toggle` was excluded
because its target state isn't known in advance without an extra read.
The result: a `toggle` HTTP dispatch that succeeded at the hub-call layer
but never actually reached the physical device (asleep repeater, brief RF
collision, a mesh device that ACKs and then drops the command) was
reported to the user as an unqualified success, with no code-level check
that anything actually changed. Untested (`tests/test_device_control_service.py`
had zero `toggle` coverage before this release).

## Fix approach

**Confirmation lifecycle:** added
`UnifiedMCPAgent._resolve_pending_confirmation()`, called at the very top
of `homebrain_agent.py`'s `process_user_request_result`, before any fast
path runs. It mirrors `ConfirmationStore.consume()`'s own semantics
exactly: if there's a pending confirmation for this session, every
message consumes it -- resuming the sensitive action if the message is a
recognised confirm word, or silently cancelling it (matching the base
orchestrator's existing "any new question cancels pending confirmation"
behaviour) if it isn't, before that message goes anywhere near a fast
path. A bare confirm word with nothing pending gets the same "No Hubitat
action is pending confirmation" message the base orchestrator already
gives. One deliberate carve-out: a confirm word ("do it") is not
intercepted by this check when a device-selection clarification (not a
sensitive-action confirmation) is the thing actually pending, so "do it"
in reply to "which device do you mean?" still gets the existing
re-prompt instead of a confusing "nothing pending" message.

**Toggle verification:** before dispatching a `toggle` command,
`DeviceControlService` now reads the device's current `switch` attribute,
computes the expected post-toggle value, and attaches the exact same
`waitFor`-based verification `on`/`off` already had, using that computed
value as the target. If the pre-read fails or the attribute isn't
reported, it falls back to the previous unverified-but-not-crashing
behaviour rather than guessing.

**Two cheap regex hardenings**, found during the same fast-path audit and
folded into this release since they're low-risk, same-file changes: the
bare/named/contextual attribute parsers in `contextual_read_fast_path.py`
now also accept `whats` without an apostrophe (common on mobile with
autocorrect off), and `parse_bare_attribute` now also matches a bare
"the temperature" with no question word at all -- both used to fall
through to the model's tool-selection loop, the exact
outdoor-weather-misrouting risk this parser exists to close.

## Found, not fixed this round

A parallel audit surfaced several more gaps, documented here rather than
rushed into this release without adequate live verification:

- `routine_control_arguments`'s scheduling guard only recognises literal
  `at <time>` phrasing -- "turn on the light every day"/"tonight"/"in 10
  minutes"/"at sunset" bypass it and execute immediately with a garbled
  device name instead of being routed to rule authoring.
- Multi-clause commands ("turn on the light and turn off the fan") get
  folded into one garbled device name rather than being split or handed
  to the model.
- `parse_device_selection` fires unconditionally (not gated on an actual
  pending clarification), so an unprompted "use the porch light" resolves
  as a device selection rather than being available to other fast paths
  or the model.
- `hub_read_diagnostics`'s blanket READ classification lets
  `hub_get_metrics(recordSnapshot=true)` and `hub_get_device_health`
  (arbitrary ping/traceroute/speedtest) execute with zero confirmation
  and zero mutation tracking, because gateway-level classification never
  inspects sub-tool arguments.
- `set_level`/`set_color`/`set_color_temperature` device commands have no
  local deterministic tool, no verification, and no numeric range
  validation before dispatch -- narration is entirely model-driven, the
  same class of gap already fixed for confirmed writes in 0.10.375, but
  here for an *unconfirmed* routine-write path.
- Several tool-effect classification helpers in `tool_registry.py`
  (`_DESTRUCTIVE_ACTIONS`'s compound entries, the action-prefix tables
  against camelCase/bare-word action names) have dead or unreachable
  branches, currently masked by fail-closed defaults elsewhere in the
  same function.

None of these currently bypass a safety-critical gate outright (most are
masked by an existing fail-closed default), but they're real correctness
or UX gaps worth a dedicated follow-up pass rather than a rushed fix
bundled into this release.

## Validation

- `python -m pytest -q` -- 651 passed (8 new: three confirmation-lifecycle
  regression tests proving a stale confirmation is cancelled by an
  unrelated fast-path turn, a fresh queue() doesn't silently clobber an
  unresolved older one, and the "do it"/device-clarification collision
  still re-prompts correctly; three toggle-verification tests covering
  convergence, non-convergence, and the pre-read-unavailable fallback;
  two regex-hardening tests for apostrophe-free "whats" and bare "the
  temperature").
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.376
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: hardest of these to verify live is the stale
  confirmation fix, since it requires a specific multi-turn sequence
  (propose -> unrelated command -> unrelated "yes") to reproduce; the
  toggle verification fix is straightforward to check with any toggle
  command and the server log.
