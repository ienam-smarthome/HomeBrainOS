# 0.10.372

## Fixed

0.10.370 tightened the system prompt to steer the model away from calling
`homebrain_weather_snapshot` for a bare, unqualified reading question like
"temperature" or "what's the temperature" -- but that fix was prompt-only,
which the changelog flagged as a tracked follow-up: "the model can still
occasionally choose the wrong tool despite the instruction." This release
closes that gap with a deterministic fast path, mirroring the existing
`contextual_read_fast_path.py` pattern used for pronoun follow-ups
("its temperature?"), named/room reads ("Bedroom 1 temperature"), and motion
aggregation.

While building it, exercising the exact wording from the 0.10.370 changelog
end-to-end (through the full agent, not just the parser in isolation)
surfaced a second, pre-existing bug in `parse_named_attribute`'s own regex:
`"What's the temperature?"` backtracked into `name="the"`, `attribute=
"temperature"` -- its optional `"(?:the\s+)?"` lead-in and required-nonempty
name group can't both be satisfied by "the temperature" without giving "the"
to one or the other, and the engine gave it to `name`. That silently routed
the request into device-name resolution for a device literally named "the",
which only ever produced a correct answer by accident when some device
happened to be labelled after the attribute word itself. Confirmed with a
full-agent integration test using a device labelled "Temperature": before
the fix, `"What's the temperature?"` answered "Do you mean Temperature?"
(a single-alternative disambiguation prompt) instead of resolving directly.

## Fix approach

Added `parse_bare_attribute()` to `contextual_read_fast_path.py`, matching
either the plain single word (`"temperature"`, `"humidity?"`) or its minimal
question forms (`"what's the temperature"`, `"show me the current power"`)
that carry no device name at all -- deliberately narrower than
`parse_named_attribute`, which requires a name between the question prefix
and the attribute. Wired into `homebrain_agent.py`'s
`process_user_request_result` right after the `named_attribute` check, so it
routes straight to the existing `_contextual_attribute_outcome()` path with
the attribute word standing in for both the requested name and the
attribute -- which reaches `DeviceQueryService.resolve_device()` unchanged,
so its existing bare-attribute disambiguation guard (0.10.369) is what
actually decides between a single exact match and a multi-reporter
clarification. This bypasses the model's tool-selection loop entirely for
this case: it can no longer choose `homebrain_weather_snapshot` for an
indoor reading no matter how the prompt is worded that day, because the
model never sees the request at all.

Also fixed the newly-discovered `parse_named_attribute` regex bug: added
`"the"`, `"a"`, `"an"` to the set of names treated as invalid (alongside the
existing pronoun-only exclusions `"it"`, `"that"`, etc.), so a bare article
can no longer be mistaken for a device name and the request correctly falls
through to the new bare-attribute path instead.

The 0.10.370 prompt-tightening text is left in place as defense in depth for
any phrasing this narrower deterministic parser doesn't cover (e.g. a named
device combined with ambiguous wording); it no longer needs to carry the
whole burden for the common bare-word case.

## Validation

- `python -m pytest -q` — 632 passed (5 new: `test_live_soak_correctness.py`
  cases for `parse_bare_attribute`'s positive/negative matches and the
  `parse_named_attribute` article-exclusion regression;
  `test_homebrain_agent.py` full-agent integration cases proving a bare
  `"temperature"` query with three indoor reporters never reaches the model
  tool-selection loop and correctly disambiguates, and that a device
  literally labelled "Temperature" still resolves directly through
  `"What's the temperature?"`).
- `python scripts/run_release_gate.py` — 627 passed
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` — 0.10.372
- `python scripts/analyze_imports.py` — `orphan_modules: []`
- Live re-check pending: re-run "temperature", "humidity", and "what's the
  temperature" against the real WebUI to confirm the response no longer
  goes through a model round at all (check the server log for the absence
  of an `Ollama streamed round completed` line on these specific queries)
  and still correctly disambiguates across the same indoor sensors as
  0.10.369 did.
