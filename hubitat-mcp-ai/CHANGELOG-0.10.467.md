# Hubitat MCP AI 0.10.467

## Reserve one bounded controller follow-up after causal room discovery

Live validation of 0.10.466 confirmed that controller candidates are now exposed by
same-room discovery, but also exposed a budget-ordering problem: the room filter
arrived on the third and normally final read round, so the generic reasoning budget
forced final synthesis before the newly discovered controller history could be read.

The supplied Bedroom 3 run therefore ended immediately after
`homebrain_filter_devices` with 3 model rounds / 8 tool calls and never executed a
button-controller history read.

### Request-local controller follow-up reservation

When an investigative room filter returns structured
`eventSourceHints.controllerCandidates`, HomeBrain now arms exactly one
request-local follow-up opportunity.

That reservation:
- temporarily prevents the normal 3-round / 8-read budget from forcing synthesis;
- allows exactly one extra read only when it is
  `homebrain_device_history` for one of the advertised controller candidates;
- requires the explicit history attribute to be one of that candidate's structured
  suggested attributes (for example `pushed`, `held`, `released`, or
  `doubleTapped`);
- is consumed after the first extra attempted read, whether valid or not, so it
  cannot become an open-ended fourth-round expansion;
- leaves mutation/confirmation safety paths unchanged.

This keeps the generic budget at 3 rounds / 8 reads for ordinary investigations
while giving controller-first causal evidence one bounded chance to complete when
the stronger source is discovered only at the budget boundary.

## Live evidence driving the change

The 0.10.466 Bedroom 3 run:
- correctly retained the five observed light intervals and 1h44m estimate;
- correctly retained the Late Night mode correlation;
- successfully completed Bedroom 3 room discovery;
- then synthesized immediately with 3 model rounds / 8 calls;
- never executed a controller history read.

## Regression coverage

Tests verify:
- controller discovery defers normal budget exhaustion;
- exactly one matching controller-history read can exceed the normal read limit;
- a sensor-history attempt cannot consume the reservation as an allowed read; and
- a controller history request using the wrong attribute is rejected as the
  reserved extension.
