# Hubitat MCP AI 0.10.463

## Temporal proof and investigative-attribute hardening

Live 0.10.462 validation showed that multi-source causal reasoning was improved,
but three generic evidence problems remained:

1. final prose could summarize only two long periods while deterministic history
   contained five observed bounded intervals;
2. a related sensor could be queried without an explicit attribute and then be
   used to support an absence claim about motion or illuminance;
3. the model could guess a sub-tool under the wrong gateway (for example
   hub_list_apps through hub_read_diagnostics).

0.10.463 addresses all three without introducing device-specific routing.

### Bounded interval proof

History evidence receipts now include the deterministic observed interval list
(start, end, duration, and clipping flags), capped at 12 intervals for API output.
The final evidence ledger renders up to eight of those intervals alongside the
count and duration reliability.

This gives synthesis the actual temporal proof rather than only a total and longest
duration.

### Interval-cardinality guard

A new API-boundary guard compares exhaustive period/interval counts in final prose
against deterministic history evidence.

If the answer says "two separate periods" while the receipt contains five observed
bounded intervals, only that contradictory sentence is replaced with the
deterministic observed count. Explicit subsets such as "the two longest periods"
remain valid.

### Explicit related-history attributes

On investigative history requests, the first successful device history establishes
the subject. Later history reads for a different device must specify the attribute
being investigated.

For example, a sensor used to test an illuminance hypothesis must be queried with
attribute=illuminance; generic device history cannot be used as evidence that no
illuminance data existed.

Rejected attribute-less related-history calls do not reach Hubitat. The model
receives a structured retry error and the request metric
investigative_attribute_required is incremented.

Unverified zero history also gets a tighter serialization boundary: wording such
as "no recorded motion data" is rewritten to the bounded zero-history statement
rather than being treated as proof of absence.

### Gateway/sub-tool compatibility

Tool discovery now remembers successful operation-to-gateway mappings. Gateway
calls are checked against:

- the live gateway schema when it enumerates operations;
- operation names exposed by the gateway description; and
- operation-to-gateway mappings learned from hub_search_tools.

A provably incompatible call is rejected before MCP execution and instructs the
model to use hub_search_tools for the exact operation rather than guessing another
gateway. The gateway_operation_rejected counter makes this visible in request
metrics.

## Live evidence driving the change

The supplied 0.10.462 Bedroom 3 investigation correctly found the Late Night mode
correlation and checked logs and related sensors, but its final answer described
only two on-periods while the deterministic receipt reported five observed bounded
intervals totaling an estimated 1h 44m.

The same run queried Bedroom 3 Sensor T1 without an attribute before concluding
that no illuminance data was available, and attempted hub_list_apps through
hub_read_diagnostics, which the live server rejected as an unknown sub-tool.

## Regression coverage

Tests cover:

- bounded observed intervals in temporal evidence details;
- correction of exhaustive interval-count contradictions;
- preservation of non-exhaustive "two longest periods" summaries;
- conservative rewriting of unverified zero motion-data absence wording;
- gateway compatibility rejection from both gateway descriptions and live
  discovery mappings; and
- investigative related-device history requiring an explicit attribute before
  the Hubitat event read is executed.
