# Hubitat MCP AI 0.10.462

## Current-turn evidence ledger and stronger investigative synthesis

Live 0.10.461 validation showed that the new investigative-history path could
produce useful multi-source reasoning, but two weaknesses remained:

1. on a long turn the final model could still occasionally claim that a source
   was not provided even though that same request had successfully checked it;
2. investigative history could fan out across several weakly related sources
   instead of preferring the strongest available provenance first.

0.10.462 addresses both without adding device-specific or question-specific answer
rules.

### Evidence-quality ladder

Investigative history now explicitly prefers evidence in this order:

1. direct provenance or native log evidence;
2. subject-linked rule/app state or app event history;
3. location/mode events close to the subject transition;
4. a small number of materially relevant related-device/sensor histories.

The model is instructed to prefer one stronger source over several weaker temporal
correlations, stop once the available evidence supports a bounded conclusion, and
avoid room-wide or whole-hub evidence sweeps merely for completeness.

Straight factual temporal questions retain the 0.10.460 evidence-sufficiency fast
path.

### Current-turn evidence ledger

Before final no-more-tools synthesis, HomeBrain now builds a compact deterministic
ledger from request-scoped evidence receipts when multiple material evidence
classes were checked.

The ledger records successful source presence such as:

- subject and related-device histories;
- location/mode history;
- native/log reads;
- rule/app reads;
- device discovery/filter results;
- live-context snapshots.

It also carries bounded temporal summaries from deterministic history and bounded
location-event examples when those details are available.

CHECKED means the source was actually supplied to the model in the current
request. It does not mean the source proved causation. This distinction is stated
explicitly in the final synthesis instruction.

A single ordinary history answer does not receive the ledger, avoiding unnecessary
prompt overhead on the established fast path.

### Source-consistency serialization guard

A narrow API-boundary guard backs up the final ledger. If the final prose explicitly
claims that a sensor/related-device, location/mode, log, rule/app, or device-history
source was not provided or checked while successful current-turn receipts prove
otherwise, only that contradictory sentence is replaced with a conservative
statement that the source was checked but did not by itself establish a cause.

The guard deliberately does **not** alter content claims such as "no motion events
were recorded": a checked source may legitimately contain no matching events.

### Location correlation auditability

Successful location-event reads now attach their bounded event rows to the
authoritative location-history receipt. This makes a final statement such as
"a Late Night mode change occurred at 01:30:02" auditable from the returned
current-turn evidence rather than visible only inside provider context.

## Live evidence driving the change

The supplied 0.10.461 Bedroom 3 investigation correctly reported an estimated
1h 44m over five observed light intervals, correlated the 01:30:07 light-off with
the 01:30:02 Late Night mode transition, considered related sensor data, and did
not promote correlation to causation.

The room-scan and request-local identity changes from 0.10.461 were also validated:
hubitat://context handled same-room discovery and two resolution-cache hits were
recorded. The remaining opportunity is therefore final evidence synthesis and
investigative source ordering rather than another device lookup patch.

## Regression coverage

Tests cover:

- final synthesis receiving the current-turn evidence ledger before the no-tools
  instruction;
- ledger entries for subject history, related-device history, and location/mode
  history including a bounded mode-event example;
- deterministic correction of a false "sensor or location data was not provided"
  claim when both sources were checked;
- preserving legitimate "no motion events were recorded" wording;
- authoritative location-event receipts carrying bounded event details; and
- the investigative-history prompt exposing the direct-provenance-first evidence
  hierarchy.
