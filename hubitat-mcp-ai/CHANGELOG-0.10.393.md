# 0.10.393

## Why this release

Fourth and final of four grouped releases closing Tier 1 findings from
the proactive full-codebase review conducted this session (0.10.390
shipped hub info & presenter string/unit accuracy, 0.10.391 shipped text
parsing & device resolution accuracy, 0.10.392 shipped Rule Machine
capability filter safety). This release covers the public API's
`session_id` default safety.

## Fixed

**A caller that omitted `session_id` on `/api/chat`/`/api/ask` shared
one session key with every other caller who also omitted it.**
`ChatRequest.session_id` previously defaulted to the literal string
`"default"`. `session_id` is the key under which a pending write
confirmation, an active disambiguation/clarification choice, and "last
device" pronoun context ("turn it off") are all tracked -- two unrelated
direct-API callers who both omitted `session_id` would silently share
that state. One caller's pending destructive-action confirmation could
be read, or even confirmed, by a completely different caller's next
request. The bundled WebUI was never affected -- it always sends its own
real per-tab UUID (`webui.py`'s `newSessionId()`) -- but any other direct
API consumer that didn't supply its own `session_id` was exposed.

`session_id` now defaults to `None` and, when omitted, each request is
given its own random, unguessable UUID (`uuid.uuid4().hex`) instead of
the shared literal `"default"`. This isolates concurrent callers who
don't supply their own session_id from each other, without requiring
existing callers (including the WebUI) to change anything.

## Validation

- `python -m pytest -q` -- 710 passed (1 new: two consecutive requests
  that both omit `session_id` are confirmed to receive distinct,
  non-"default" session keys).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.393
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes finding #8, the last Tier 1 item from the
  full-codebase review conducted this session. All four grouped releases
  (0.10.390-0.10.393) are now complete.
