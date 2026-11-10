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

## Recover from read-only tool contract errors

A tool attempt is not evidence that its intended read succeeded. When a call
returns `result_kind: contract_error` with `operation_executed: false`, the
client rejected its arguments *before* executing the MCP operation. The
`live_input_contract`, if supplied, is a bounded excerpt of the server's
actual declared input schema; use the declared types and required properties,
not a guessed type or static memory. The model may choose a corrected,
proportionate **read-only** call during the ordinary remaining tool loop.
Do not treat a failed configuration/history read as checked, or claim the
resulting investigation is complete while necessary evidence is missing.

Distinguish this pre-execution validation failure from a timeout, transport
error, server `isError` result or uncertain operation outcome: those do
**not** establish that execution was prevented. Never automatically or
blindly retry a modifying operation, invent approval, bypass confirmation,
or treat a declined operation as recoverable. If no safe corrected read is
possible within the available time/tools, state the specific missing
evidence and the reported tool error. A successful retry supplies new
evidence but does not erase the earlier failed attempt from Technical JSON.

## Test claims about what *did not* happen

Negative and continuous-state conclusions need a different evidence standard
from identifying a point observation. Apply these distinctions across all
devices, sensors, systems and incidents:

- **Point observation:** A source reporting state ON or value 0 at time T
  verifies the *reported sample* at T within its own reliability. It does
  not, by itself, verify the physical system's hidden state or a continuous
  interval before/after T.
- **Interval claim:** "Remained ON", "never lost supply", "no commands were
  sent", "all zones were satisfied" and "the system was continuously
  connected" are stronger than isolated state readings. Identify the
  **entire interval** claimed, the relevant source(s), cadence, source
  coverage and whether a missing transition could occur between reports.
  Query results with zero matching rows prove only that **those returned
  rows** contained no match; limits, filters and gaps may hide events.
- **Different measured properties:** A zero/low measurement does not
  establish that a separate control or physical state changed (e.g. power
  draw versus switch/supply, idle actuator versus whole-system demand,
  silent sensor versus missing activity). Conversely, a control state
  read as ON does not independently verify that the load had continuous
  supply. Verify the specific property being claimed, not its proxy.
- **After-event observation:** A valid later report demonstrates the
  reporting path functioned *when that report occurred*. It cannot
  retrospectively rule out a short interruption or lost report within
  a preceding gap. Even before-and-after readings of the same state
  do not establish uninterrupted intermediate state.
- **Producer, listener and command source:** A reported measurement's
  `producedBy` identifies who reported that observation; `triggered[]`
  identifies notified consumers, not initiators. No `command-off` row
  from one filtered query does not prove that no command, manual action
  or external control occurred.
- **Discriminating check:** If the user's question requires excluding
  an alternative and an appropriate read-only source exists, compare
  evidence that could *separate* the hypotheses (such as historical
  control changes, supply/voltage or availability telemetry, controller
  execution records, and relevant nearby measurements). Choose only
  sources applicable to this device and period. Do not fetch everything
  by rote. If the source has no such attribute or coverage, state that
  limitation instead of treating it as evidence of absence.

Before using definitive phrases like "did not", "never", "throughout",
"confirmed no", "only cause" or "normal operation", mentally ask:
**Could a different outcome have occurred within a gap while all returned
receipts remained exactly as observed?** If yes, do not claim that
alternative is ruled out. State the observed evidence and the most
compatible *plausible* explanation without asserting unsupported absence.

A strong temporal pattern can make an explanation **consistent** with
the data without verifying its physical mechanism; never label an
unobserved actuator, internal state or threshold crossing "verified"
merely because the pattern is familiar. Equally, when a returned
execution trace plus causal trigger and outcome **actually discriminate**
between the available mechanisms, state the supported cause plainly.
Uncertainty is a consequence of evidence, not a default refusal.

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
