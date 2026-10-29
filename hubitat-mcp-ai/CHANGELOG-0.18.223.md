# Hubitat MCP AI v0.18.223 — Room-source evidence frontier

## Live motivation

The first v0.18.222 Bathroom question took 54.384 seconds and failed:
a successful hub_list_rooms returned 25 rooms but V2's projection discarded
`rooms` as an unknown field. The model then attempted an unbounded
hub_list_devices request, which timed out after 20 seconds, and finished with
six independently verified name candidates but zero individual device reads.

This is a general source-adapter/planner defect, not a named-device exception.

## Change

- Project the real `rooms` list into a bounded, source-name-only catalogue.
  Ignore embedded room-list device IDs or metadata as unverified membership.
  Preserve source count, duplicates, rejected rows and completeness limits.
- Expose the verified list and room names appearing in the *original question*
  to the model's ordinary live READ transcript, with a suggestion to inspect
  that room via a live-advertised `hub_get_room`, then read individual
  source-authorised device IDs. The model still chooses all operations.
- Once the model has a real room catalogue matching the requested name and
  the live tool manifest supports a targeted room operation, reject an
  unbounded whole-device listing as a redundant investigation path. The
  rejected proposal is recoverable feedback, not a hidden tool action.
- Keep explicit distinction among room names, room membership and independent
  current-state reads. No local text route or automatic room/device WRITE.
- Add a synthetic end-to-end replay of the exact former failure trajectory
  (list rooms -> unbounded list attempt -> name resolution -> room detail ->
  individually verified states). The fake model still chooses all reads.
- Preserve normal production Main Ask and write confirmation policy.

## Tests

`pytest -q tests/test_investigation_v2_room_source_frontier_0_18_223.py`

Run the complete Python CI suite and release assurance before merge.

## Live test after update

1. "Which Bathroom lights are currently off? Check the actual Bathroom
   room membership and include lights without Bathroom in their names.
   Read only; change nothing."
2. Verify that `verified_room_name_catalogs` contains Bathroom, a targeted
   `hub_get_room` read occurs where offered, individually verified lights
   appear in the answer, and NO `hub_list_devices` timeout occurs.
3. Compare concise answer against room-inventory membership and the
   ID-matched device receipts. Report incomplete group coverage explicitly.

This release does not solve the independent historical cause synthesis,
automation identification or model-fallback issues visible in the other
four live traces. Those warrant additional general architecture work.
