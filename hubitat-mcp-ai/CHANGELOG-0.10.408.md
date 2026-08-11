# 0.10.408

## Why this release

Ships the four Tier 3 (low confidence/severity/cosmetic) findings from the
2026-08-10 full code review -- the last outstanding items on that review.

## Fixed

**`webui.py` JSON-embedded the configured page title (and version) into an
inline `<script>` block via `json.dumps()`, which does not escape a literal
`</script>` sequence.** A title containing that exact string could break out
of the script tag, letting anything that followed it be parsed as raw HTML
instead of a JS string literal. Only reachable via admin/add-on config
(`web_title`) today, not a remote-input surface, but the fix is cheap and
correct regardless of where the value originates. Both the title and
version values now have every `</` escaped to `<\/` before being
interpolated -- a standard, harmless JS string escape that keeps the exact
same string value while removing the literal closing-tag byte sequence from
the markup.

**`deterministic_tool_presenter.py`'s battery-filter branch
(`homebrain_filter_devices` with `attribute="battery"`) rendered the raw
device attribute value with a hardcoded `%` suffix and no unit-dedup
guard**, unlike this same file's home-snapshot low-battery aggregation
(fed by `device_query_service.py`, which explicitly strips a pre-existing
`%` before parsing). A device reporting battery as an already-suffixed
string (`"45%"`) rendered as `"45%%"`. Now strips a pre-existing `%` before
re-appending one, mirroring the established pattern instead of diverging
from it.

**`contact_history_queries.py`'s own datetime parsing didn't carry the
offset-without-colon regex fix `natural_datetime.py` already has.**
`natural_datetime.format_natural_datetime()` rewrites a trailing
colonless UTC offset (e.g. `"+0100"`) to the colon form before calling
`datetime.fromisoformat()`, required on Python 3.10 and earlier. This
module's own `parse_event_datetime()` (shared with `location_event_queries.py`,
which imports it directly) carried a separate, bare `.replace("Z", "+00:00")`
with no such guard -- currently inert on the deployed Python version, but a
latent inconsistency if that reliance ever changes. The offset
normalization is now a single shared, exported helper
(`natural_datetime.normalize_iso_offset()`), used by both
`format_natural_datetime()` and `parse_event_datetime()`, so the two can't
drift apart again.

**`contextual_read_fast_path.py` had no dedicated test file at all**
(`tests/test_contextual_read_fast_path.py` did not exist) -- a coverage
gap, not a known live bug. Added a full test file covering every exported
function, including a test that documents (rather than silently
"fixes blind") the one real gap it surfaced: `present_attribute()` has no
guard against an already-unit-suffixed value, unlike the battery-filter fix
above and the home-snapshot aggregation it mirrors. No current call site
passes an already-suffixed value into `present_attribute()`, so this is
coverage of the gap's existence for future reference, not a live bug fix.

## Validation

- `python -m pytest -q` -- 836 passed, including all four new/updated test
  files (`test_webui_render_contract.py`, `test_deterministic_tool_presenter.py`,
  `test_contact_history_queries.py`, and the new
  `test_contextual_read_fast_path.py`). The three genuine-bug regression
  tests (webui escape, battery double-`%`, offset-without-colon) were each
  confirmed to fail against the pre-fix code via `git stash` before being
  included.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.408
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
