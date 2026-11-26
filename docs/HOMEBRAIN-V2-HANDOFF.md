# HomeBrain V2: handoff notes (26 Nov 2026, add-on 2.0.0-alpha.209)

Read this first in a new chat, then `CLAUDE.md`, then `docs/HOMEBRAIN-V2-ALPHA-HISTORY.md` (tail).

## Goal

HomeBrain should reason like Claude does with the same Hubitat MCP tools: pick the right call, read the
result, answer calibrated, and be fast. The owner (iEnam) does not want a stream of one-off patches.
Prefer structural changes (fewer layers, better tool surface, measured model choice) over wording.

## Where things are

- Add-on: `hubitat-mcp-ai-v2/` (alpha series). Model: nemotron-3-super via Ollama Cloud.
  Hubitat MCP Rule Server 5.2.1, gateway mode ON (gateway tools take `tool` + `args`).
- Repo: ienam-smarthome/HomeBrainOS. Work in `/home/claude/homebrainos`.
- Prompt profiles: `upstream` (default, ~8k tokens, upstream skill + short client contract) or `legacy`.
- Home specifics: Hue bridge Matter id 7790 (lights are its components; parent verification needed);
  HADB Bridge 6959 supplies occupancy from Home Assistant; apps 4013 "Bathroom (Lights On)" and 4012
  "Hallway" set levels; Cudy "Block ..." switches in room Internet (ON = allowed, OFF = blocked);
  Shower Light 7807 is in room Bathroom but its label has no "bathroom".

## Workflow conventions (learned the hard way)

- Branch from `origin/main`, never from an old local branch: squash merges rewrite SHAs and a branch
  carrying the earlier commit conflicts (this cost PR #1799).
- `gh pr create` fails in Claude Code sessions (GraphQL 403). Use
  `gh api repos/ienam-smarthome/HomeBrainOS/pulls -f title=... -f head=... -f base=main -f body=...`
  and `gh api -X PUT repos/.../pulls/N/merge -f merge_method=squash`.
- Force-push is blocked by the session classifier. If history is rewritten, push a new branch name.
- Standing authorization: merge only when all 10 CI checks are green (check run count must be 10;
  3 means the PR is conflicted or workflows did not run).
- Before every commit: `python scripts/validate_addon.py`, `python -m pytest -q` from `hubitat-mcp-ai-v2/`
  (1039 tests). `analyze_imports.py` reports 15 pre-existing orphan modules (offline evaluation code).
- Version bump touches: README.md, hubitat-mcp-ai-v2/README.md, config.yaml, rootfs/app/ui.html,
  rootfs/app/app.py, tests test_command_first_ui, test_claim_delta_review, test_frozen_evaluation_mobile,
  test_v2, test_model_routing, test_ollama_cloud, and an entry appended to the alpha history doc.
- Rules from CLAUDE.md that matter: no `_v2`/`_fixed` module variants; gate on tool name and structured
  arguments, never on user wording. Known violation to retire: `routine_action_fastpath._SIMPLE`
  and `control_surface_recovery.is_explicit_device_imperative` read the question.

## Test method: HomeBrain vs Claude on the same hub

- Sheet (Claude's answers, behaviours to copy, untested areas):
  https://claude.ai/artifact/NA3uBVfV4Bb3t1JtRwYskT
- `scripts/run_test_sheet.py --base-url http://<ha>:<port> --out sheet.json` runs the six read-only
  questions (1, 3, 4, 5, 6, 7; add `--bathroom-time HH:MM` for 8) in fresh conversations and prints
  wall time, rounds, native calls, failures, peak prompt tokens and the answer head per question.
  Write questions (lights, blocks, Q2, Q9) still need the in-app approval card.

## Results on alpha.206 (first full comparison)

| Q | Question | Result |
|---|---|---|
| 1 | Which lights are on? | Correct, 3 reads, 19 s, 110k input tokens. Claude: 1 call. |
| 2 | Bathroom on, scope only | Failed: no tool call, only "No action queued". Cause unknown (text was not logged; alpha.208 adds `unprepared_replaced_text`). |
| 3 | What changed in the last hour? | Honest but thin: asked location events only. Did not use `changedSince` on `hub_list_devices`. 27 s, source review and audit rounds. |
| 4 | List the block devices | Failed: published "My draft stands as written." Fixed in alpha.208. |
| 5 | Hub health and uptime | Good, 4.7 s. |
| 6 | Which batteries are low? | Good (Fridge Door Contact 2%). |
| 7 | Which devices have gone quiet? | Figures right. Missed that HADB Bridge and both LWR01 batteries went silent in the same minute; guessed "orphaned/test artifacts" for the redundancy heartbeat devices. Asked for all 174 healthy rows (+12k tokens). |
| 8 | Why did bathroom lights come on at 14:08? | Best answer, calibrated, matched Claude (occupancy 14:08:26.062 then Light 1 at .153; no command row). But 123 s, 10 rounds, 18 calls, 3 errors. |
| 9 | Hallway on/off | Off fine. On was a no-op (read already showed on at 14:28:42) yet the answer said it changed and called the write snapshot "independent read-back". Fixed by the alpha.209 guard (below). |

Claude-side reference facts for this hub: Shower Light is found by `roomFilter: "Bathroom"` +
`capabilityFilter: "Light"`; stale devices include Backup Hub Active and Lighting Automation Heartbeat
(~99 days, lighting-redundancy project); Fridge Door Contact battery 2%.

## What shipped

- alpha.205: single-command no-call falls through to the normal path.
- alpha.206: upstream prompt profile; client contract notes on labelFilter vs roomFilter.
- alpha.207: wrongly shaped focused-round call falls through once (`single_command_fallthrough: call_not_eligible`).
- alpha.208: acknowledgement after a compute check no longer replaces the answer; `unprepared_replaced_text` telemetry.
- alpha.209: already-in-state guard. A single plain on/off command is refused (once per device and command
  per request) when this request's own read already shows that switch state. Uses tool name, arguments and
  receipts only. Lifecycle status `already_in_requested_state`, no card, model answer kept. A resend of the
  identical call is allowed (still through approval), so a stale bridge state cannot dead-lock a request.
  Prewrite review is skipped for a call the guard will refuse.

## Direction (replaces patching)

The captures show the cost of layers, not a lack of rules: source review, claim audit, causal follow-through,
compute nudge, prewrite review and the routine fast path each add rounds, rewrite or replace the model's
answer, and each has produced a bug (alpha.208's acknowledgement, "No action queued" replacing an answer).
Claude itself is a plain tool loop with permission gates.

1. Add a `loop_profile` option like `prompt_profile`: `full` (today) and `plain` (tool loop + hard gates only:
   write approval/confirmation, repeat and in-state guards, redaction, deadline). No source review, audit,
   nudge, prewrite review or fast path in `plain`. Run the sheet on both and keep only layers that measurably
   improve answers. Telemetry already records which layers fired.
2. Model and tool-surface A/B on the sheet: nemotron-3-super vs a stronger model; gateway vs flat tools;
   `hub_list_devices` `format: context`/`fields`/`attributeNames` guidance. Peak prompt tokens (35k-90k) and
   rounds per answer are the speed levers.
3. Cut prompt cost: do not offer ~41 tools every round; keep the leaf-schema fetch, drop unused categories.
4. Retire question-reading code (`_SIMPLE`, `is_explicit_device_imperative`) by deciding from the selected
   call and the receipts, per CLAUDE.md rule 2.
5. Extend the runner with write cases once approvals can be driven from the API (`/api/activity/{id}/confirm`).

## Open items

- Shower Light missed on room-wide requests (model filters by the word "bathroom").
- Q2 no-tool-call cause (read `unprepared_replaced_text` after re-running on alpha.208+).
- `changedSince` unused for "what changed"; hub uptime arithmetic and battery wording nits.
- Telemetry nit: `component_parent_source_read_count` reports 0 although the parent is read.
- waitFor on writes not built; protected-device list for NucBox/router block risk.
- Untested vs Claude: Rule Machine/rule writing, block/unblock writes, bathroom write (occupancy app 4013 interferes).
