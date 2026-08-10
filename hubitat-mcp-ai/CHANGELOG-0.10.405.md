# 0.10.405

## Why this release

**Correction to 0.10.404.** That release concluded the "Front Door" bare-query
zero-events report was a timing artifact, not a bug -- the user has since
confirmed this was wrong: the door was genuinely opened and closed several
times that morning, and the query was asked in the afternoon, well inside
the trailing 24-hour window. Re-investigated directly against the live hub:
device resolution, the `attribute="contact"` server-side filter, and the
`hoursBack` window calculation in `hub_list_device_events` all check out
correctly for this exact device right now, so the app-side logic that can be
tested in isolation is not reproducibly broken. What *is* fixable and
confirmed live is a related gap: any "last opened/closed"-style question
phrased without a leading "when did" fell through every deterministic fast
path into the general model tool-calling loop, which (a) answers from
`homebrain_device_history`'s default 24-hour window instead of the
dedicated fast path's 7-day window, and (b) renders the full raw event list
instead of one direct sentence -- both of which the user separately flagged
("front door last opened" returned nine bullet points; the user asked for a
direct answer instead). Widening the fast-path match closes both gaps for
every phrasing that reaches it, and reduces the exposure of the underlying
zero-events risk by using the far more forgiving 7-day lookback instead of
24 hours for this pattern.

This bundle also carries two fixes prepared earlier in the same review pass:
a live-observed location-privacy redaction gap and a device-claim-grounding
false-positive, both already individually verified before this release.

## Fixed

**"Last opened/closed" questions without a "when did" prefix missed the
direct-answer fast path.** `homebrain_agent.py`'s `_last_contact_request`
only matched "when did NAME last open/close(d)". Phrasings such as "front
door last opened" or "when was front door last opened?" fell through to the
general model loop, which answers via the generic, 24-hour-windowed
`homebrain_device_history` tool and lists every event instead of stating the
answer directly. Two new patterns -- `_LAST_CONTACT_WHEN_WAS` ("when was
NAME last opened/closed") and `_LAST_CONTACT_STATEMENT` (the bare statement
form, with a negative lookahead so it never swallows "why did .../when
did .../was ..." questions handled by their own patterns) -- now route these
phrasings to the same direct-answer path as "when did NAME last open?",
which reads a 7-day window and answers with one sentence, e.g. "Front Door
last opened at 7:15 am on Monday 10 August 2026."

**Location-privacy redaction missed the hub's own home postal code.**
`location_privacy.py`'s `SENSITIVE_LOCATION_KEYS` covered coordinates,
addresses, map tiles, and journey logs, but not `zipCode` -- live-confirmed
on this hub's own Hub Info device (`"zipCode": "SE13 7SD"`), the same
category of precise-location PII as a street address. Added `zipcode`,
`zip`, `postalcode`, and `postal_code` to the redacted key set. (The
originally-suspected `currentValue`-vs-`value` gap in the same module was
investigated against real live device data during this pass and found not
to exist in the actual Hubitat wire format -- no code change was needed for
that part.)

**Device-claim grounding falsely flagged answers about a device whose label
is a prefix of another device's label.** `device_claim_grounding.py`'s
`find_named_device_mismatch` matched device labels in list order; when one
device's label is a prefix of another's (e.g. "Front Door" vs. "Front Door
Sensor"), a correct, fully-evidenced answer about the longer-labelled device
still matched the shorter label as a valid word-bounded substring, flagging
a device the answer never actually named. Now matches longest labels first
and treats a shorter label's match as already accounted for once it falls
entirely inside a longer label's match span, so the false positive is gone
while a genuine mismatch (including a different, unrelated device named in
the same answer) is still caught.

## Validation

- `python -m pytest -q` -- 781 passed (6 new: 3 for the last-contact
  phrasing broadening in `test_homebrain_agent.py`, 3 for the
  device-claim-grounding prefix-collision fix in
  `test_device_claim_grounding.py`).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.405
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live-verified against the real hub: `hub_list_device_events` with
  `attribute="contact"` and without both return the same event set for the
  Front Door device; `redact_precise_location` now redacts a live
  `zipCode` attribute entry.
