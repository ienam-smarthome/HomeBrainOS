# Hubitat MCP AI 0.10.465

## Transition-aware location correlation

Live validation of 0.10.464 exposed a synthesis contradiction. The subject history
showed a Bedroom 3 Light interval ending at 01:30:07.971 while current-turn
location history contained a Late Night mode change at 01:30:02.403, about 5.6
seconds earlier. The final answer nevertheless said the location/mode history did
not show a correlating event.

The underlying evidence was present. The compact final evidence ledger simply kept
the newest six location events, which omitted the older but materially closer Late
Night transition.

### Correlation-aware evidence ledger

Location-event hints are now ranked by temporal proximity to the subject's observed
bounded interval starts/ends before the remaining hint slots are filled in normal
newest-first order.

Tight matches are explicitly marked as near a subject transition so final synthesis
cannot lose a materially relevant older mode event just because several newer
location events exist.

### Final-answer correlation guard

A narrow serialization guard now checks categorical statements that current-turn
location/mode history contains no correlation. If deterministic evidence contains a
location event within 15 seconds of an observed subject interval boundary, the
contradictory sentence is replaced with the concrete timing relationship plus the
required caveat that temporal correlation does not establish causation.

This does not invent causation and does not create a correlation when the nearest
event lies outside the tight proximity window.

## Live evidence driving the change

The 0.10.464 Bedroom 3 run:
- correctly preserved five observed Bedroom 3 Light intervals and the estimated
  1h44m total;
- had Late Night mode at 01:30:02.403 and the light interval ending at 01:30:07.971;
- nevertheless claimed there was no mode/location correlation;
- used 3 model rounds and 9 tool calls, so this release fixes evidence selection
  rather than increasing the global reasoning budget.

## Regression coverage

Tests verify:
- detection of the 5.6-second Late Night/light-off proximity;
- transition-near events outrank the newest-six ledger truncation;
- categorical false no-correlation wording is corrected at serialization; and
- no correction is applied when the location event is outside the tight window.
