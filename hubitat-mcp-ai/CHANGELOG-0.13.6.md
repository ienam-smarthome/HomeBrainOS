# Hubitat MCP AI 0.13.6

## Causal boundary fidelity and open-interval evidence

0.13.6 follows the first successful 0.13.5 live causal run.

0.13.5 fixed request-class contamination and reduced the Bedroom 3 investigation
from eight model rounds / 37.4 seconds to four model rounds / 20.9 seconds. The
live run also confirmed the known-history fast path, host-owned room/controller
plan, window-bound location history, and direct installed provenance registry.

The same run exposed three evidence-fidelity gaps:

1. a physical controller event recorded approximately 54 ms after a light interval
   ended was described as correlating with the earlier turn-on;
2. a later active transition with no observed closing transition was known by the
   temporal analyser but dropped from the final evidence receipt; and
3. the single provenance round had no installed-app identity context, so the model
   chose native logs only and did not inspect relevant app/rule configuration in
   the same round.

## Directional controller boundary evidence

Controller proximity is no longer treated as an undirected timestamp distance.

For every controller event close to a subject interval, HomeBrain now determines
which observed boundary is nearest:

- START boundary
- END boundary

The evidence carries:

- boundary role;
- interval index;
- absolute delta;
- signed delta;
- controller event timestamp/value/description; and
- physical metadata when upstream explicitly reports it.

A controller event nearest an interval END is never exposed as turn-on provenance.
It is rendered separately as `end-controller` evidence.

The compatibility `controller_transition_alignments()` view remains available,
but it now returns START alignments only.

## Causal timeline boundary roles

`causal_timeline.py` now separates:

- `triggerEvidence` / `start-provenance`;
- `endControllerEvidence` / `end-controller`;
- subject start/end command events; and
- mode/context correlation.

Materiality may still include an end-aligned controller event, because it is useful
causal evidence for the interval end. It does not change `triggerStatus`, which
remains unresolved unless START provenance exists.

The final synthesis contract explicitly states that an END controller event is
turn-off/end-adjacent evidence and cannot be cited as the cause of an earlier
turn-on.

## Deterministic controller-boundary validator

New module:

- `controller_correlation_guard.py`

The validator detects a final draft that combines a controller/physical-push claim
with trigger/cause/provenance wording for an interval that has only END-aligned
controller evidence.

It supplies a localized correction baseline and lets the shared no-tools repair
pass preserve the rest of the reasoning.

## Preserve unbounded/open active transitions

The temporal analyser already avoided inventing a duration when an unverified
event stream ended with an active transition and no later inactive row.

0.13.6 now preserves the missing evidence explicitly:

- `unboundedActiveInterval`
- `openActiveInterval`
- `openActiveStart`
- `openActiveStartNatural`

`unboundedActiveInterval` means a recorded active transition had no observed
closing transition before the analysed window ended.

`openActiveInterval` is the stronger ongoing-window form; it does not assert that
the device physically remained active continuously.

These fields are carried into technical evidence receipts and the current-turn
evidence ledger.

## OPEN causal timeline rows

An unbounded active start now becomes a material `OPEN` causal timeline row.

Example semantic shape:

`[MATERIAL OPEN] 12:01 am -> no observed closing transition; duration=not established`

This means a current active transition cannot disappear merely because HomeBrain
correctly refuses to invent an exact interval duration.

The causal-subject sufficiency gate also treats an unbounded active start as real
current-turn subject evidence, so a why/cause investigation can continue to
controller/provenance checks even when no complete bounded interval exists yet.

## Causal app/rule navigation in the same provenance round

When material turn-on transitions remain unresolved after the host controller and
location layer, HomeBrain now loads the cached installed-app manifest before the
single bounded provenance model round when `hub_read_apps_code` is installed.

The manifest is explicitly navigation context, not causal evidence.

This gives the model concrete app IDs/names early enough to issue up to two
complementary read-only provenance calls in the SAME model round, for example:

- native device logs; and
- one relevant app/rule detail/config read.

The model is instructed not to spend the round listing apps again.

Metric:

- `causal_app_navigation`

## Regression coverage

0.13.6 adds tests for:

- a physical button event nearest an interval end not appearing as turn-on
  provenance;
- END alignment carrying signed and absolute deltas;
- the causal timeline rendering `end-controller` separately from
  `start-provenance`;
- the synthesis validator repairing end-boundary controller misattribution;
- an unverified ongoing active transition retaining its exact recorded start;
- an OPEN material causal timeline row with no invented duration;
- the evidence ledger preserving the open transition;
- open active starts satisfying the causal subject evidence gate; and
- the `causal_app_navigation` metric.

## Live acceptance target

Repeat the same Bedroom 3 causal question on 0.13.6.

Expected:

- request class remains `live-read`;
- four model rounds remains the target when logs + app/rule detail are selected in
  the same provenance round;
- the 23:10 physical push is associated with the interval END/turn-off boundary,
  not the 23:10 turn-on;
- any recorded active transition with no observed closing transition is mentioned
  separately as open/unbounded, without an invented duration;
- unresolved material transitions may use installed app/rule identity context in
  the same bounded provenance round;
- no return to fuzzy device/sensor exploration; and
- final synthesis distinguishes turn-on provenance, turn-off provenance,
  downstream automation/config effects, weaker mode correlation, and unresolved
  transitions.
