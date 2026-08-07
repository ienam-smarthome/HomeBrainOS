# Hubitat MCP AI 0.10.355

## Fixed

- **A mixed tool-calling round silently dropped its routine action.** When
  the model bundled a routine action (e.g. "turn off the kitchen light")
  and a sensitive action (e.g. "lock the front door") in the *same*
  tool-calling round, the whole round correctly deferred to confirmation --
  but `ConfirmedActionCoordinator.resume()` only replayed the sensitive
  actions list afterward. The routine action from that round was never
  executed, never re-queued, and produced no error: the light silently
  stayed on while the lock got confirmed and ran. For non-Rule-Machine
  sensitive actions this also left the routine call's `tool_call_id`
  unanswered in the message history replayed back to the model, which some
  chat-completion APIs reject outright.

  Fixed by queuing the *entire* tool-calling round (routine actions
  included, in the model's original order) once any action in it requires
  confirmation, rather than queuing only the sensitive subset. On confirm,
  `resume()` now replays every action from that round, so the routine one
  actually runs and every `tool_call_id` gets a matching reply. The
  confirmation prompt's wording and its action-count limit are still
  judged against the sensitive subset only, so a routine call riding along
  is never described as "sensitive" or counted against
  `DEFAULT_MAX_CONFIRMATION_ACTIONS`.

## Context

Found during a full architecture re-review of `mcp_agent_orchestrator.py`'s
tool-call loop (no live report or open PR triggered this -- it was found by
reading the mixed-effect branch directly against the "does a round persist
enough state to replay itself" question). `ConfirmationStore.queue()` was
already designed to store the whole `messages` history and `assistant_
message`, which already carried every tool call the model made -- only the
`actions` list being scoped down to just the sensitive subset caused the
gap. Reusing the full round for `actions` closes it without changing the
store's or the coordinator's shape.

## Validation

- `python -m pytest -q` -- 571 passed, including a new regression test
  (`test_mixed_round_replays_the_routine_action_after_confirmation`) that
  queues a routine `hub_manage_devices` call alongside a sensitive
  `hub_restart` call in one round, confirms neither executes before
  confirmation, and asserts both run in original order afterward with the
  confirmation wording naming only the sensitive action.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.355.
- `python scripts/analyze_imports.py` -- zero orphan modules.
