# Hubitat MCP AI 0.16.38

## Refine reporting-source causal answers

Live Hallway testing on 0.16.37 showed that the causal evidence was correct but
the concise presentation still hid several useful distinctions.

For a Matter-reported Hallway Light 1 ON transition, HomeBrain correctly found:

- no aligned direct Hubitat command producer;
- no matching `pushed` event from either checked Hallway dimmer;
- repeated FP300 and Soft Sensor motion correlations;
- both motion sources reported through the same Matter Aqara M3 path;
- the requested motion events arrived after the light boundary.

The answer exposed the correlation counts and shared path, but it did not show the
requested event deltas, did not surface the negative controller result, and ended
with a generic correlation limit instead of an explicit unresolved-initiator
conclusion.

## 0.16.38 behavior

Reporting-source causal summaries now:

- show each motion/presence source's bounded match count;
- state whether the requested sensor report arrived before or after the requested
  subject transition, with a compact delta;
- explicitly report when the checked controller candidates have no matching
  button event at the requested boundary;
- preserve the shared-producer warning when multiple sensors are reported through
  the same upstream bridge;
- finish with **Exact initiator unresolved** when Hubitat has no direct command
  producer, while keeping outside-Hubitat automation/action as a possibility
  rather than asserting a cause.

This is presentation-only refinement. It does not change correlation windows,
candidate selection, provenance precedence, or the focal-transition contract.

## Metrics wording

The technical metrics row formerly labelled `MCP HTTP` is now labelled
`Aggregate MCP HTTP`.

MCP HTTP calls can overlap, so their summed transport time can legitimately exceed
the wall-clock `Total` request duration. The new label makes that distinction
clear without changing metric collection.

## Regression coverage

New tests cover:

1. the live-shaped 5/6 FP300 and 6/6 Soft Sensor Hallway pattern;
2. requested sensor timing rendered as before/after the subject transition;
3. explicit negative controller-check wording;
4. the unresolved-initiator conclusion;
5. aggregate MCP HTTP timing displayed alongside a shorter wall-clock total.
