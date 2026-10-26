# HomeBrainOS v0.18.144 — Source-grounded V2 automatic device matching

Investigation V2 could fail with HTTP 422 ("Device name does not uniquely match
the live Hubitat inventory") even when the user named the correct device in the
question. The previous path treated the AI semantic planner's proposed
`device_name` as though it were an explicit operator override, allowing a
shortened, stale or wrong model name to replace the original question.

## Behaviour

- For automatic investigation and duration requests, first match device
  references in the actual user question against independently retrieved
  live Hubitat names and IDs. Use longest whole-name matches.
- Only when the question contains *no matching device name* can a model-proposed
  name be used, and it must exactly and uniquely match live inventory.
- A genuinely ambiguous name (including duplicate labels across two Hubitat
  IDs) still fails closed. V2 does not arbitrarily choose one; use a full
  distinct name or the explicit verified ID override in Advanced.
- Operator-provided Advanced name and ID inputs still use strict existing
  checks, but collapsed Advanced fields are no longer silently submitted.
  Reopen Advanced to deliberately apply an override.
- HTTP errors display beneath the Run button with wrapping, not crammed
  horizontally beside it.

Regression tests cover incorrect and abbreviated AI names, independent
question matching, genuinely duplicate labels, cross-device questions,
browser Advanced state and explicit ID overrides.

This does not change production V1, Hubitat devices/automations, browser
authentication, device writes, or MCP tool permissions. No keyword-based
special cases or hard-coded Hubitat IDs were introduced.
