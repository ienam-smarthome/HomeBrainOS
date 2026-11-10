# Evidence-driven causal investigations (general reasoning reference)

Use this method when explaining **why** a physical state, command, automation
decision, alarm, heating call, network event or measured change happened.
It applies across domains; it is **not** a device-specific rule, fixed tool
sequence, deterministic validator or requirement to fetch every source.

## Establish the focal event before explaining it

- Identify the specific event and its **source timestamp and time zone**.
  Distinguish a **command issued** by a controller, a **state reported** by
  a bridge/device, and an app that merely **received** a subsequent event.
  A command-to-state sequence can verify the recorded issuer without proving
  why the controller made its decision.
- Name the **scope actually inspected**: query boundaries, filters, returned
  count, limit reached, earliest/latest returned event and relevant gaps.
  An empty query proves only that this query returned no rows, not that no
  action occurred or that history exists continuously.
- Read configuration as a **snapshot at retrieval time**, unless a source
  establishes its settings at the historical event time. A description of a
  possible mechanism does not itself prove that mechanism executed.

## Test explanations against time and alternatives

Before promoting a candidate mechanism to "the cause", perform a short
**hypothesis-to-observation consistency check**:

1. **Prediction:** If the candidate is a delay, schedule, threshold or
   state-dependent rule, what earlier state or event and what time range would
   have to occur to make the focal event happen? Use concrete timestamp
   arithmetic when the timing semantics are actually established. For a
   simple uninterrupted delay of D ending at T, the candidate start is T-D.
   Do **not** assume a timer was uninterrupted, nor infer its start from
   its configured duration alone.
2. **Comparison:** Check whether the predicted starting event/state was
   observed, contradicts a returned observation, falls in a queried window
   with no returned rows, or falls **outside** the inspected lookback.
   "No rows" never proves a transition was outside the window; and a
   proposed pre-window transition does not explain a later short timer
   without evidence of a reset, re-arm, scheduling delay or another mechanism.
   Be alert to mismatched time zones, units and clock resolution.
3. **Alternatives:** Consider other configured or observed control paths
   that could produce the same result (e.g. a scheduled check, manual command,
   external controller, retry or failsafe), without inventing unconfigured
   paths. Ask whether the available evidence **discriminates** among them.
4. **Next step:** When a proportional read-only source can decide between
   plausible causes, seek it: relevant prior state/transition, controller
   configuration or event-specific execution logs. If source coverage is
   missing, conflicting or unavailable, stop at "unverified" and name the
   specific discriminating evidence. Do not retry a failed write or trigger
   a device action to reconstruct past history.

## Communicate the actual certainty

Use precise layers in the final answer:

- **Direct observation:** "App A issued off() at T; bridge B reported OFF at U."
- **Configured behaviour:** "The current app settings permit a delayed OFF."
- **Event-specific explanation:** "That delay caused this OFF" **only** when
  relevant trigger/state and temporal or execution evidence support it.
- **Unresolved:** "The issuer is verified, but which internal condition
  issued the command is not established." Do not call one candidate "the
  only plausible cause" merely because other candidates were not recorded.

Do not force a verbose template for simple factual questions. Prefer a short,
useful answer with calibrated certainty, and avoid excess reads once the
requested level of certainty is already supported. The model chooses sources,
tests its own predictions and determines whether to investigate further.
