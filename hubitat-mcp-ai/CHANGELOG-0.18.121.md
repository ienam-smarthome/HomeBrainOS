# HomeBrainOS 0.18.121 — Overnight historical evidence integrity

## Problem observed

In a read-only investigation of a past overnight lighting interval, the latest-N native Hubitat history returned only later events. The model concluded that no earlier ON event was recorded, inferred that the controller did not know the light was ON, and attributed the incident to a hub restart and severe load. The records did not support that causal chain.

## General changes

- A **shared calendar-boundary resolver** converts requests containing two explicit UK dates/times into UTC ranges, correctly handling the BST/GMT transition and rejecting ambiguous repeated-hour instants.
- The model's existing read-only tool planning receives the canonical interval and an explicit reminder to use **target-scoped history, commands and app logs**, not location history as a substitute.
- A **source-typed retention assessment** compares the requested incident against the oldest actual returned target switch event. If the earliest retained event is newer than the requested incident, the final API boundary does not publish an invented missing-ON/controller-timer causal verdict, even when the model gives it high confidence.
- Historical verdicts still distinguish observed hub restarts/load from proof they caused a device fault. A separately verified focal archive remains authoritative rather than being erased by later native event retention.
- The limits are attached to the existing technical investigation coverage. No additional model calls, mutating Hubitat tools, or brittle named-light sensor-routing cases.

## Testing

Regression coverage checks overnight UTC conversion, transition offsets, ambiguous clocks, fully evicted historical intervals, correctly retained focal events, archive preservation, noncausal paths, and final shared-API enforcement.
