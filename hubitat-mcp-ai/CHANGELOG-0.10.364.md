# Hubitat MCP AI 0.10.364

## Fixed

Four bugs found in a live practical-test pass against the real hub, three
of them device-resolution/data gaps and one a response-quality gap. All
four were reproduced first, root-caused against real live device data
pulled directly from the hub via a Claude MCP connection, then fixed
deterministically and covered with regression tests built from the real
device shapes involved.

- **"Turn off the fridge" failed to resolve despite an exact label match.**
  `device_target_resolver.py`'s `_GENERIC_NAME_TOKENS` set (words excluded
  from the "specific token" compatibility check) did not include English
  articles. "the fridge" normalizes to "thefridge", not equal to "Fridge",
  so it fell through to fuzzy scoring -- where "the" was then treated as a
  required *specific* identifying token that had to match something in the
  candidate label. Since no device label contains "the", this capped an
  otherwise-strong 0.8 match down to 0.69, below the 0.70 confidence floor,
  producing a false "no candidate was similar enough" refusal alongside
  unrelated candidates like "Freezer (MQTT)". Fixed by adding "the", "a",
  "an" to `_GENERIC_NAME_TOKENS` -- they carry no identifying information
  about which device is meant, exactly like the existing generic
  device-kind words ("light", "switch", etc.) already excluded there.
- **"Turn off Bedroom 1" turned off one unrelated device instead of the
  room.** A real smart plug is labelled "Bedroom1 (MQTT)" and lives in the
  "Sockets" room; its label normalizes to the exact same string as the
  room "Bedroom 1" once its "(MQTT)" qualifier is stripped for comparison.
  The model has no dedicated way to say "this is a room, not a device
  name," so it put "Bedroom 1" into `device_names`, and ordinary per-name
  fuzzy resolution -- which has no room awareness at all -- matched it
  straight to that one plug instead of the room's actual lights. Fixed in
  `device_control_service.py`: when a lone `device_names` entry exactly
  matches a real room name from the live device inventory, it is now
  treated as the room-wide action it overwhelmingly means in natural
  speech, before per-name resolution ever runs.
- **"Is Tahmid home?" answered "I don't see anyone named Tahmid," even
  though he's a real, currently-tracked (just away) Life360 member.**
  `DeviceQueryService.home_snapshot()`'s `presence` field only ever lists
  people who ARE currently present -- an away person is omitted entirely,
  not listed with an away status -- so a specific-person question about
  someone away had zero evidence to work with, and "no evidence" read as
  "this person doesn't exist" instead of "he's not home." Fixed by adding
  a new `tracked_presence` field listing every presence-capable device
  regardless of status, each with an explicit `home: true/false`, and
  updating the system prompt to point named-person presence questions at
  it instead of the home-only `presence` list. `presence` itself is
  unchanged, so nothing that already worked (whole-home "who's home"
  summaries) is affected.
- **Power-usage questions silently summed monitored smart-plug wattages
  and never touched the real whole-house smart meter**, producing a
  plausible-sounding but wrong total (148.3W from monitored plugs vs. the
  meter's actual 231W). Root cause: the Octopus Energy sensors (imported
  via Home Assistant) report their reading only through a `valueStr`
  attribute ("231 W") with the ordinary `value` attribute always null --
  a pattern also seen on other Home-Assistant-bridged sensors, not just
  Octopus. Nothing recognised `valueStr`, so these devices looked
  state-less everywhere: the shared `device_attributes()` canonicalizer,
  the compact device manifest sent to the model, and any numeric
  aggregation built on top of it. Fixed at the shared root:
  `device_state_summary.device_attributes()` now backfills a null `value`
  from `valueStr`'s leading number when one parses out, benefiting every
  consumer (contextual reads, `homebrain_query_devices` ranking,
  `home_snapshot`) at once; `agent_prompt_policy.render_device_manifest()`
  also now recognises `value`/`valuestr` as manifest-worthy attributes, so
  these sensors show a `Current:` line at all instead of appearing blank.

## Context

Found via a structured live-test pass: nine natural-language prompts run
against the real deployed app, cross-checked against ground truth pulled
directly from the Hubitat hub over a separate Claude MCP connection
(device attributes, room membership, rule health). Six of nine were
already correct (device-name disambiguation for a device/socket pair with
near-identical labels, contact-sensor and temperature-sensor reads,
outdoor-vs-indoor temperature routing) and needed no change.

## Validation

- `python -m pytest -q` -- 607 passed, including 8 new regression tests
  built from real device shapes pulled from the live hub:
  `test_leading_article_does_not_block_an_otherwise_exact_match`,
  `test_articles_a_and_an_do_not_block_exact_matches_either`,
  `test_room_name_in_device_names_acts_on_the_room_not_a_lookalike_device`,
  `test_home_snapshot_tracked_presence_includes_away_people_too`,
  `test_null_value_backfills_from_valuestr_when_numeric`,
  `test_null_value_with_non_numeric_valuestr_is_left_null`,
  `test_real_numeric_value_is_never_overwritten_by_valuestr`,
  `test_render_device_manifest_surfaces_valuestr_only_sensors`.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.364.
- `python scripts/analyze_imports.py` -- zero orphan modules.
