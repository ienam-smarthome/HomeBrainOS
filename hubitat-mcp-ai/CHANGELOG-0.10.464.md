# Hubitat MCP AI 0.10.464

## Capability-grounded investigative history

Live validation of 0.10.463 confirmed that bounded interval proof and interval
cardinality were fixed, but exposed one narrower investigative-history gap.

The model now had to provide an explicit related-device attribute, but an explicit
attribute could still be irrelevant to the resolved device. In the supplied Bedroom
3 run, `Bedroom 3 Sensor T1` was queried with `attribute=motion` even though its
useful advertised measurement is illuminance. The same response then said "No motion
events were recorded" even though the zero temporal result came from an unverified
event stream.

### Attribute capability grounding

`DeviceHistoryService` now checks well-known requested history attributes against
the resolved device's advertised attributes and capabilities before calling
`hub_list_device_events`.

A provably unsupported attribute is rejected locally with the device's available
attributes/capabilities and a retry instruction. Sparse or custom-driver metadata
remains permissive, and unknown/custom attributes are not rejected.

Examples:
- a device advertising illuminance + temperature rejects `motion`;
- `illuminance` remains valid for that device;
- a MotionSensor capability permits `motion` even if the current attribute map is sparse.

New metric: `history_attribute_rejected`.

### Conservative zero-event wording

The final serializer now also catches attribute-level phrases such as:
- "No motion events were recorded";
- "No motion activity was observed";
- "No illuminance readings were found".

When the corresponding temporal receipt has zero bounded intervals on an
unverified event stream, those claims are replaced with the existing deterministic
bounded-history statement: no bounded active interval was established from the
retrieved rows, and that does not prove the device stayed inactive.

## Live evidence driving the change

The 0.10.463 Bedroom 3 validation:
- correctly exposed five bounded Bedroom 3 Light intervals;
- correctly retained the estimated 1h44m total;
- no longer attempted `hub_read_diagnostics -> hub_list_apps`;
- explicitly queried related-device attributes;
- but queried Bedroom 3 Sensor T1 for motion and narrated its unverified zero result
  as "No motion events were recorded."

## Regression coverage

Tests cover:
- rejecting motion for an illuminance/temperature sensor;
- accepting illuminance on the same sensor;
- accepting motion from a MotionSensor capability even with sparse attributes;
- preserving unknown/custom driver attributes; and
- rewriting "No motion events were recorded" for unverified zero temporal history.
