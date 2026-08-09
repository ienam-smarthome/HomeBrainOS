# 0.10.387

## Why this release

Live-tested "check the hub health status": the WebUI's own screenshot of
the hub's Hub Info page showed `DB Size: 126 MB`, but the assistant's
answer read "Database Size: 126 KB" -- and also added a "Cloud Backup:
Successful" line with no corresponding field anywhere in the tool result
it was built from. Reported live with two screenshots and the raw response
JSON, flagging the mismatch directly ("Database Size is 126 MB not KB !").

## Fixed

**"Check the hub health status" was answered entirely by free-text model
prose, with no deterministic grounding for units or facts at all.** This
request had no dedicated fast path (unlike firmware status/install, which
already route deterministically through `homebrain_hub_info_snapshot` --
see 0.10.x history). It reached the model unfiltered, which chose a raw
`hub_read_diagnostics`/`hub_get_metrics` call and then wrote its own
summary from the result. The underlying Hubitat data was correct -- the
model just mislabelled the unit while composing prose -- and, separately,
invented a "Cloud Backup: Successful" line that traces to no field the
tool actually returned.

The fix adds a `parse_hub_health_intent()` classifier (mirrors
`parse_firmware_status_intent()`) that routes "check the hub health
status" and close variants to a new deterministic
`UnifiedMCPAgent._hub_health_outcome()`, built on the same
`homebrain_hub_info_snapshot` tool the firmware fast paths already use.
`hub_info_service.py` already tags every relevant field with its actual
reported unit (`database_size_unit`, `free_memory_unit`,
`temperature_unit`) -- this path formats those fields directly instead of
handing the raw numbers to a model and hoping it picks the right unit
word. Every line in the response now traces to a real field in the
snapshot; nothing is reported that the snapshot didn't return, and no
alert is invented or suppressed.

## Validation

- `python -m pytest -q` -- 694 passed (3 new: the exact live scenario --
  a 126 MB database size, reported with an explicit unit -- comes back as
  "126.0 MB" with no "KB" anywhere in the message and no fabricated
  "Cloud Backup" line; a hub reporting real active alerts surfaces them
  instead of a generic "healthy" headline; `parse_hub_health_intent`
  matches the WebUI's own quick-action button text and close natural
  variants without over-matching broader hub/firmware questions).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.387
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "check the hub health status" should report the
  database size (and every other figure) with the hub's own actual
  reported unit, and should never include a claim not backed by a real
  snapshot field.
