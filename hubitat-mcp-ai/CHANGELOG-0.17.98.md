# 0.17.98 — Historical command denial cross-check

- Fixes a known false negative from 0.17.97: evidence included a 12 October command-on, but the answer claimed `No switch=on or command events were recorded for 12 October 2026`.
- Evidence ledger recognises this mixed command/state denial and replaces it with source-grounded command details.
- Explicit absence of an event **at 08:16** remains unresolved, since a 07:25 command does not establish causality at 08:16.
- Adds regression coverage for both cases; no additional cloud calls or Hubitat writes.

Limit: still a bounded linguistic contradiction detector, not a general semantic verifier or automatic paid escalation.
