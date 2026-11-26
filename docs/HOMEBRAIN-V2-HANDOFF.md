# HomeBrain V2: handoff notes (26 Nov 2026, add-on 2.0.0-alpha.210)

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
  (1059 tests). `analyze_imports.py` reports 15 pre-existing orphan modules (offline evaluation code).
- Version bump touches: README.md, hubitat-mcp-ai-v2/README.md, config.yaml, rootfs/app/ui.html,
  rootfs/app/app.py, tests test_command_first_ui, test_claim_delta_review, test_frozen_evaluation_mobile,
  test_v2, test_model_routing, test_ollama_cloud, and an entry appended to the alpha history doc.
- Rules from CLAUDE.md that matter: no `_v2`/`_fixed` module variants; gate on tool name and structured
  arguments, never on user wording. Known violation to retire: `routine_action_fastpath._SIMPLE`
  and `control_surface_recovery.is_explicit_device_imperative` read the question.

## Test method: HomeBrain vs Claude on the same hub

- Sheet (Claude's answers, behaviours to copy, untested areas):
  https://claude.ai/artifact/NA3uBVfV4Bb3t1JtRwYskT
- `scripts/run_test_sheet.py --base-url http://<ha>:<port> --profile both --out sheet.json` runs
  questions 1 to 7 (add `--bathroom-time HH:MM` for 8) in fresh conversations, each in `full` then `plain`,
  and prints profile, wall time, rounds, native calls, failures, peak prompt tokens, declined cards and the
  answer head. Needs alpha.210 or later (it checks before asking anything). It turns auto-approval off and
  declines every card, so nothing is sent; question 2's proposed command is in `cards_declined`.
  `<port>` is the add-on's direct port (off by default, no Home Assistant login): switch it off afterwards.
  Question 9 and other real writes still run in the app.

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

1. Built in alpha.210: `loop_profile` = `full` (default) or `plain` (see "The plain profile" below). Next:
   run the sheet on both and keep only the layers that measurably improve answers. Telemetry records which
   layers fired. One run per question on a live home is noisy, so repeat any close result.
2. Model and tool-surface A/B on the sheet: nemotron-3-super vs a stronger model; gateway vs flat tools;
   `hub_list_devices` `format: context`/`fields`/`attributeNames` guidance. Peak prompt tokens (35k-90k) and
   rounds per answer are the speed levers.
3. Cut prompt cost: do not offer ~41 tools every round; keep the leaf-schema fetch, drop unused categories.
4. Retire question-reading code (`_SIMPLE`, `is_explicit_device_imperative`) by deciding from the selected
   call and the receipts, per CLAUDE.md rule 2.
5. Extend the runner with write cases once approvals can be driven from the API (`/api/activity/{id}/confirm`).

## The plain profile

Keeps: approval cards and the configured auto-approval policy (verified lights, internet block), catalog,
leaf-schema and argument checks, identical-read and detailed-inventory refusals, repeat-write and
already-in-state guards, one-off rule and current-evidence automation denials, cursor and argument repair,
the notes attached to tool results, redaction, deadline. It also sends no native write when no approval
gate is attached.

Drops: every extra model round (reviews, audit, follow-throughs, nudges, recoveries, empty-reply retry,
deadline finalisation), the single-command fast path and post-write readback, templated early answers, the
partial-ranking hold-back (the warning stays), question-based context compaction, and all answer rewrites
and footnotes except the physical-effect note and the "no device command was sent" line.

Trade-offs to watch when comparing:
- `full`'s single-command fast path stops a model that picks a different device from the one it verified.
  In `plain` the auto-approval policy alone decides, and it does not match the target to the wording, so a
  wrong ordinary light can be sent without a card (also true of `full` outside that fast path).
- No check of "why" and history claims before publication. Judge these answers by hand.
- A single verified light write in `plain` goes through the batch light policy.
- The "no command" line still uses the question-text classifier that `full` uses (item 4 below).

## Open items

- Shower Light missed on room-wide requests (model filters by the word "bathroom").
- Q2 no-tool-call cause (read `unprepared_replaced_text` after re-running on alpha.208+).
- `changedSince` unused for "what changed"; hub uptime arithmetic and battery wording nits.
- Telemetry nit: `component_parent_source_read_count` reports 0 although the parent is read.
- waitFor on writes not built; protected-device list for NucBox/router block risk.
- Untested vs Claude: Rule Machine/rule writing, block/unblock writes, bathroom write (occupancy app 4013 interferes).
