# Hubitat MCP AI 0.13.3

## Current-turn causal evidence fence

0.13.3 follows a live 0.13.2 validation that exposed a grounding contradiction.

The current Bedroom 3 Light history for the requested "last night" window reported:

- intervalCount = 0
- observedIntervals = []
- coverage = partial
- durationReliability = unverified-event-stream

Yet final synthesis reconstructed two older overnight light-on intervals and
attributed them to historical physical dimmer presses.

Those controller events still existed in the current controller history, but the
current-turn subject history no longer established matching light transitions.
The causal conclusion therefore exceeded the current request's subject evidence.

### Conversation history is context, not evidence

Tool selection may still use bounded conversation history so follow-ups such as
"what about that light?" remain understandable.

Final investigative synthesis now applies a stricter boundary:

- keep the system prompt;
- locate the latest non-HOST user request;
- keep that request and all later current-turn assistant/tool/HOST messages;
- exclude all earlier user and assistant conversation turns;
- build the concrete tool packet from that same current-turn slice.

The evidence ledger and causal timeline were already request-local; this change
prevents an older assistant conclusion from being visible beside them during the
final reasoning pass.

### Subject timeline is a prerequisite for causal expansion

New `subject_has_observed_intervals()` checks the deterministic current-turn subject
history before controller provenance planning.

For a causal request, if the first resolved subject history contains no bounded
observed interval:

1. HomeBrain does not run exact-room controller discovery;
2. it does not fetch button/sensor/location/app/rule/log evidence to reconstruct an
   older or hypothetical subject timeline;
3. it records `causal_subject_empty_stop`;
4. it immediately enters shared final synthesis using current-turn evidence only.

This is deliberately conservative.

An unverified empty interval set does **not** prove the device stayed off or inactive;
the final answer must preserve that caveat. It only means HomeBrain does not have a
current-turn subject transition to which auxiliary provenance can be causally
aligned.

### Why controller history alone is insufficient

A physical button event is strong provenance only when it aligns with an observed
subject transition in the same current-turn evidence set.

Historical button events without a current subject interval remain legitimate facts
about the controller, but they cannot establish that this device changed state in
the requested window.

## Metrics

Adds:

- `causal_subject_empty_stop`

## Regression coverage

0.13.3 adds tests for:

- zero observed subject intervals rejecting causal alignment;
- requiring bounded start+end timestamps before subject interval sufficiency;
- current-turn final-synthesis slicing removing previous user/assistant conclusions;
- an empty subject timeline staying empty even when historical controller events are
  present;
- FinalAnswerCoordinator never exposing the previous assistant causal conclusion to
  the final no-tools model call; and
- the new causal-subject-empty metric being accepted by RequestMetrics.

## Live acceptance target

Repeat the same Bedroom 3 causal question while the current history page still no
longer contains the earlier overnight light transitions.

Expected behavior:

- the request should stop after the subject history rather than reading the dimmer,
  location history, or downstream automation provenance;
- `causal_subject_empty_stop=1`;
- no old 00:02 / 01:32 light interval should be reconstructed from conversation
  history or controller history alone;
- the answer should state that no bounded on interval was established from the
  current recorded rows while preserving the unverified-stream caveat; and
- model/tool rounds should fall substantially because the invalid causal expansion
  is skipped.
