# Hubitat MCP AI 0.10.466

## Controller-first causal evidence selection

Live validation of 0.10.465 confirmed that transition-aware mode correlation is
working and latency returned to a healthier level, but causal investigations still
spent related-device budget on environmental sensors while newly exposed
same-room button controllers were ignored.

In the supplied Bedroom 3 run:
- Bedroom 3 Light history correctly established five observed intervals and the
  estimated 1h44m total;
- the Late Night mode correlation was preserved correctly;
- room discovery completed successfully;
- T1 was still queried for motion and the Soft Sensor for motion;
- no same-room button/dimmer/remote event history was checked.

A separate grounded investigation with those controllers in scope showed that
button events can align essentially exactly with the unexplained light-on
transitions, making controller event history materially stronger causal evidence
than motion or illuminance correlation.

### Same-room event-source hints

Room-filter results now expose a bounded `eventSourceHints.controllerCandidates`
list for devices whose advertised capabilities indicate button/controller
behaviour.

Each candidate includes:
- stable id and label;
- advertised button capabilities; and
- suggested explicit history attributes derived from those capabilities, such as
  `pushed`, `held`, `released`, and `doubleTapped`.

Environmental sensors are not labelled as controller candidates.

### Controller-first investigative contract

For why/cause/trigger investigations, the host evidence-quality contract now ranks:
1. direct provenance/log evidence;
2. rule/app evidence tied to the subject;
3. close location/mode events;
4. same-room button/controller/remote event history when room discovery exposes it;
5. environmental sensor histories.

After a room filter returns controller candidates, the reasoning loop explicitly
instructs the model to check the smallest materially relevant controller history
before weaker motion/illuminance correlation and to compare those event timestamps
with the subject's observed transition times.

A close button event remains corroborating evidence rather than automatic proof of
who physically pressed the control.

## Scope

This release does not add another global read round and does not hard-code Bedroom
3 device names. Selection is driven by advertised capabilities in the room-filter
result.

## Regression coverage

Tests verify that:
- Pushable/Holdable/DoubleTapable button devices receive the appropriate suggested
  event attributes;
- illuminance and motion sensors are not misclassified as controllers;
- plain Button capability falls back to `pushed`; and
- candidate hints remain bounded.
