# 0.17.7 — Evidence-anchored focal-event investigations

The 0.17.6 live test asked why Bathroom Light 1 turned on at **07:53:36**. HomeBrain established app 4013 -> setLevel(50), and configured LWR01 motion occurred 79 ms before the command. However, its second log read drifted to **07:08**, it re-read app configuration because host-collected facts were not visible to the model, and final synthesis was pushed into an unnecessary five-interval timeline by the global coverage validator.

This release fixes the shared **investigation focus** for any device, not the Bathroom app specifically:

- An explicit user time containing seconds is matched against observed start/end device-history boundaries. Only a **single unambiguous** match narrows the causal timeline; ambiguous or absent time retains normal broad-history behavior.
- Causal log-window normalization for a matched single event continues to query that event even after prior successful host log reads. Broad multi-event investigations retain the established bounded multi-window behavior.
- The final synthesis and timeline completeness validator now require only the requested material event where a focal boundary is identified; whole-day totals and tables are no longer mandatory for one-event questions.
- Host-prefetched app configuration and timestamp-scoped log results are recorded as bounded, sanitized evidence facts and passed into the deep model's current-turn context. The model is instructed not to repeat completed reads without a specific missing field.
- Read-only behavior, live MCP availability and write confirmation gates remain unchanged.

**Limit:** Exact-clock focus currently requires one unambiguous HH:MM:SS in the question and an observed matching event. Questions about older events without a reliable unique boundary must still avoid assuming that the latest event is the user's target. Model reasoning quality and live MCP data coverage require additional validation.
