# Hubitat MCP AI 0.10.468

## Broaden same-room controller discovery beyond strict room metadata

Live validation of 0.10.467 showed that the reserved controller follow-up was never
armed. The request reached Bedroom 3 room discovery and then completed without a
controller-history read, which means no structured controller candidate was exposed
from that filter result.

The likely structural gap is that newly exposed button controllers can be visible to
MCP without carrying complete Hubitat room metadata. 0.10.466 only derived
controller candidates from devices whose `room` matched the requested room exactly.

### Room-first, label-affinity fallback

For room-filter investigations, HomeBrain now evaluates button-capable devices from
the full live context and ranks candidates by:

1. exact room metadata match; then
2. clear label affinity with the requested room when room metadata is absent or
   incomplete.

For example, a button-capable device labelled `Bedroom 3 Dimmer` can now be surfaced
as a Bedroom 3 controller candidate even if its `room` field is empty.

The fallback remains bounded and conservative:
- the device must advertise a button-related capability;
- environmental sensors are never included merely because their label contains the
  room name;
- exact room matches rank ahead of label-affinity matches;
- candidate hints include `matchBasis` so the provenance of the association remains
  auditable.

Once such a candidate is exposed, the 0.10.467 one-read controller reservation can
arm normally and the model can check a suggested explicit attribute such as
`pushed`.

## Live evidence driving the change

The 0.10.467 Bedroom 3 run:
- correctly resolved the light and retained five observed intervals / estimated
  1h44m;
- completed Bedroom 3 room filtering;
- completed four model rounds and nine tool calls;
- never executed controller history and ended without a controller candidate being
  consumed.

## Regression coverage

Tests verify:
- exact-room button controllers rank first;
- button-capable labels matching the requested room are included when room metadata
  is missing;
- unrelated-room controllers are excluded; and
- non-controller sensors are not pulled in by label affinity alone.
