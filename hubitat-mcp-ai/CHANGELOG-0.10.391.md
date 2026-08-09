# 0.10.391

## Why this release

Second of four grouped releases closing Tier 1 findings from the
proactive full-codebase review conducted this session (0.10.390 shipped
the first: hub info & presenter string/unit accuracy). This release
covers text parsing and device resolution accuracy -- three
independent, previously-unreported bugs in how free-text requests are
parsed and how a matched device's own reported unit is looked up.

## Fixed

**"What is the current battery" (and similar "current <attribute>"
phrasing with no device name) misread the qualifier word "current" as
the device name itself.** `parse_named_attribute`'s regex has an
optional `(?:current\s+)?` group specifically to swallow that qualifier,
but when nothing else precedes it in the sentence, the required-nonempty
`name` capture group has no other text to claim and the engine assigns
it "current" instead of leaving it for the qualifier group. Live-
reproduced: `parse_named_attribute("What is the current battery")`
returned `("current", "battery")` instead of `None`, sending a
no-device-named request down the named-device-resolution path for a
device literally called "current". `"current"` now joins the existing
`_PRONOUN_NAMES` exclusions (`"it"`, `"the"`, `"a"`, `"an"`, etc.), so
these requests correctly fall through to the bare-attribute reading
instead.

**A trailing "please" on a control or internet-access command polluted
the captured device/target name.** Every capturing regex in
`request_classification.py` already strips a *leading* optional
"please" (e.g. "please turn on the tv"), but none of them accounted for
"please" trailing the sentence instead (e.g. "turn on the tv please",
"block the tv please") -- that trailing word was captured as part of the
device/target name, breaking device-name matching. A new
`_strip_trailing_please()` helper now strips it from both
`routine_control_arguments()`'s captured target and
`parse_immediate_internet_access_intent()`'s captured target, while
leaving a device genuinely named "Please Do Not Disturb Light" untouched
(the strip only fires on a trailing, whitespace-separated "please", not
one that's part of a longer word or name).

**Attribute units were always read from a small hardcoded table,
ignoring what the matched device itself actually reports.**
`DeviceQueryService._unit_for()` previously took only the attribute name
and looked it up in a fixed `{"battery": "%", "humidity": "%", "power":
"W", "temperature": "°C"}` table -- a Fahrenheit-configured
temperature device would have its own `71 °F` reading mislabeled as
Celsius. `_unit_for()` now takes the matched device and its
attributes/states/currentStates list and prefers the unit the device
itself reports for that attribute, falling back to the hardcoded table
only when the device reports none. Two call sites in
`homebrain_agent.py` that still used the old single-argument signature
were updated to pass the device dict through.

## Validation

- `python -m pytest -q` -- 706 passed (3 new: "current" no longer
  misread as a device name across bare and named-attribute phrasing;
  trailing "please" no longer pollutes a captured device/target name,
  with a negative case confirming a device genuinely named "Please Do
  Not Disturb Light" is unaffected; a device's own reported unit, e.g.
  `°F`, is now preferred over the hardcoded fallback table).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.391
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes findings #4-6 from the full-codebase review
  conducted this session. Rule Machine capability-filter safety and the
  public API's session_id default are tracked separately as the
  remaining two grouped releases.
