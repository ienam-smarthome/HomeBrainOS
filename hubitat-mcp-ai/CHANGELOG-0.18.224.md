# Hubitat MCP AI v0.18.224 — Concise, independently verified room answers

## Live evidence

The 29 October v0.18.223 Bathroom retest completed in **11.270 seconds**
(previous run **54.384 seconds**) with 5 successful READs and no failed
tool calls. It verified the actual Bathroom room contains 8 members.
Independent individual reads reported three lights off:
Bathroom Light 1, Bathroom Light 2 and Shower Light.

The live result exposed two output defects:
- Without a separate name-prefix lookup, the host treated every room member
  as a room-only "extra", repeating all three lights and reporting a misleading
  `room_only_count=8`.
- The displayed room answer was independently joined from verified room and
  device receipts, yet its answer-level validation issues incorrectly reflected
  an unused model claim-selection protocol (`unstructured_withheld`).
- Five other room members had no independent device detail reads; they must
  remain explicitly unverified without overwhelming a light-status response.

## Implementation

- Room-first investigations now print independently read devices once and do
  not invent an additional room-only group when no name-match baseline exists.
  Name-first investigations still distinguish genuine room-only extras.
- Unread room members remain visible as a concise coverage count in room-first
  answers; their capabilities and states are **not** asserted or inferred.
  Names remain in source receipts for audit.
- Answer-level `validation_issues` now refer to the actual displayed,
  host-verified room/device synthesis, including unread/partial membership
  limitations. The model claim-selection outcome is preserved unchanged under
  `native_diagnostics.claim_publication`, with a new
  `used_for_display_answer` flag distinguishing an unused protocol.
- Existing read-only V2 permission, source verification, source receipts,
  causal attribution policy and production Main Ask controls are unchanged.

## Testing

`pytest -q tests/test_investigation_v2_room_answer_quality_0_18_224.py`

Includes a replay of the live five-read path: 25 room names, eight Bathroom
members, three separately verified off lights and five unread members.
Additional tests cover name-first extras without duplicate presentation,
and the model/host publication authority distinction. All automated checks
must pass before promotion to the add-on.

## Limits and next development

This is answer-quality and provenance reporting work, not evidence that
Livingroom Light 1 causal investigations or heating timer analysis are now
correct. Those require deeper autonomous source-follow-up and temporal
reasoning tests against real event windows.
