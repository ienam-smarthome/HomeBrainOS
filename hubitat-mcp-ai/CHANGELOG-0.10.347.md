# Hubitat MCP AI 0.10.347

## Fixed

- **Scheduled rule requests could fabricate a success message without
  creating anything.** Live testing of 0.10.346 against a real hub found
  that "turn off livingroom light 1 every day at 10:40am" (and the
  equivalent one-time phrasing) returned "I have scheduled a daily rule to
  turn off Livingroom Light 1 every day at 10:40am" with `success: true`,
  but `hub_list_rules` and `hub_get_jobs` on the live hub showed no such
  rule and no matching scheduled job -- nothing was ever created. The
  response's own evidence trail confirmed it: only read/discovery tool
  calls were recorded (`hub_read_devices`, `homebrain_resolve_device`,
  four `hub_search_tools` calls, two `hub_get_tool_guide` calls) --
  `hub_set_rule` was never called.

  Root cause: `RuleAuthoringService.propose()` -- the deterministic
  compiler that turns recognised schedule phrasing into a validated
  `hub_set_rule` call and queues it for confirmation -- refuses to run
  unless `hub_manage_rule_machine` is already present in
  `catalog.declared_names`, the small subset of tools currently exposed to
  the model this turn. That subset only grows to include the Rule Machine
  gateway if the upfront `hub_search_tools` discovery call -- run with the
  raw user prompt as its query -- happens to surface it. A BM25 search
  over control-language phrasing like "turn off livingroom light 1 every
  day at 10:40am" does not surface `hub_manage_rule_machine` (verified
  live: the top 5 results were `hub_shutdown`, `hub_call_device_command`,
  `hub_create_variable`, `hub_list_modes`, and `hub_update_mcp_settings`
  -- none of them Rule Machine), even though the schedule grammar itself
  parsed perfectly. `propose()` silently declined, and the request fell
  through to the generic model tool-calling loop, where the model tried
  (and, per the evidence trail, failed within its round budget) to
  rediscover the gateway itself, then narrated a fabricated success
  message instead of reporting failure.

  `RuleAuthoringService.propose()` never asks the model to call
  `hub_manage_rule_machine` itself -- it calls the MCP server directly via
  `DeviceQueryService` and queues the resulting action through the normal
  sensitive-action confirmation pipeline (`rule_proposal_confirmation.py`).
  The `declared_names` gate was therefore checking the wrong thing: not
  "does this server have the tool" but "did an unrelated search happen to
  mention it." Changed the gate in `mcp_agent_orchestrator.py` to
  `catalog.available_names` -- every tool the connected MCP server
  actually has, independent of what the incidental discovery search
  returned.

## Context

- This is a correction to the scheduling feature shipped in 0.10.346, not
  a new capability. The regex-based schedule grammar
  (`RuleAuthoringService._intent()`) was already correct and was verified
  standalone in the previous release's tests; the bug was entirely in how
  the orchestrator decided whether that grammar was allowed to run.
- The existing unit test
  (`test_rule_authoring_uses_deterministic_compiler_before_model`) did not
  catch this because its fake `hub_search_tools` always returns a
  `hub_manage_rule_machine` match regardless of the query, which is more
  generous than the real search engine's behavior for control-language
  prompts.

## Added

- `tests/_entity_first_orchestrator_cases.py`:
  `test_rule_authoring_reachable_when_search_discovery_misses_gateway` --
  full orchestrator-level regression test using a fake `hub_search_tools`
  that deliberately does *not* surface `hub_manage_rule_machine` (mirroring
  the real search engine's behavior observed live), asserting the
  deterministic compiler still runs, queues a real confirmable
  `hub_set_rule` action, and that zero model calls happen (`ai.requests ==
  []`) -- proving nothing was fabricated.

## Scope, stated honestly

- This fixes the *dispatch* bug that made scheduled-rule requests silently
  no-op while claiming success. It does not change anything about the
  still-open, previously documented question (see the 0.10.346 changelog)
  of whether a one-time Rule Machine trigger with a full-date `atTime`
  might still internally re-fire (`"recurring": true` job label observed
  on the underlying Hubitat scheduler despite the full date). That remains
  unconfirmed and unrelated to this fix.
- The generic model tool loop's tendency to narrate a plausible-sounding
  completion message when it exhausts its round budget without a
  confirmed write is a separate, more general concern this fix does not
  address system-wide -- it only ensures the one high-traffic path
  (scheduling) that was hitting it now takes the deterministic route
  instead and never reaches that loop at all.

## Validation

- `python -m pytest -q` -- 559 passed (558 from 0.10.346 + 1 new).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.347.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Live-verified against the reported failure: `hub_search_tools` called
  directly with the exact failing query
  ("turn off livingroom light 1 every day at 10:40am") against the real
  connected hub confirms the top 5 results do not include
  `hub_manage_rule_machine`, reproducing the exact discovery gap this fix
  closes.
