# HomeBrainOS v0.18.448 — Generic causal answer presentation and proof discipline

## Source-real motivation

The user's read-only Livingroom Light 2 multi-source investigation
identified a reported OFF state at 20:53:25 GMT on 6 Nov 2026 and did
not confidently attribute the transition to a downstream SenseCap event
listener. However, its visible prose repeated a long causal source-role
explanation three times. It also said an OFF command was "captured in the
device's event history" without exposing the matching command issuer,
source event and timestamp in the displayed answer. No full Technical JSON
for this causal test was supplied in that user turn, so command/event source
coverage and exact causal claims are **not independently audited** here.

## Generic implementation

- The normal API final answer serializer runs a narrowly scoped presentation
  clean-up AFTER existing graph-backed evidence and contradiction guards.
  Within one prose section, it removes only exactly repeated long
  sentences (minimum 72 normalized characters). It does not use fuzzy
  similarity or remove different timestamps, actors, qualifiers or
  conclusions. Each heading starts a new scope.
- Markdown list items, tables, quoted lines and code fences remain untouched.
  Write requests and pending confirmation messages bypass the clean-up
  entirely, preserving command and approval instructions.
- Technical JSON records `evidence_validation.repeated_long_prose_removed`
  only when at least one long sentence was removed. This counter is a
  presentation correction, not evidence that the causal question was solved.
- The generic model system policy explicitly distinguishes state-report
  producedBy bridges, triggered[] listeners, command-off issuers, app-log
  execution and upstream triggers. The model may claim an issued command
  was recorded only when the source has a matching typed command event;
  log absence is not evidence of a command, and reporter != initiator.
- Independent synthetic regression tests cover multiline repeated causal
  prose, preserving a genuinely new timestamp/negation/source, Markdown
  tables/lists/fences, heading resets, ordinary answers, API correction
  counters, and write/confirmation exemption.
- Does not introduce additional MCP reads, device writes, paid provider
  selection, source-specific incident logic or watchdog changes.

## Evidence boundary and next test

This release cannot independently verify the most recent OFF command owner
or causality from a screenshot alone. The screenshot's visual duplication
is a demonstrated presentation failure; the availability/attribution of
typed command event and log receipts remains unverified. No invented cause
or new incident-specific hypothesis is encoded.

After required CI and merge, install the tagged v0.18.448 add-on and run
one fresh read-only causal question on a real device, supplying the full
Technical JSON. Verify a single concise causal boundary, preserved timeline
and competing hypotheses, a positive command issuer only when corroborated
by the exact source receipt, or an explicit unresolved conclusion otherwise.
No change to Hubitat/HA/router/installed addon was performed by repository
development.
