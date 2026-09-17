# Hubitat MCP AI 0.10.455

## Live-read follow-up hardening

This release addresses the specific follow-up and aggregate regressions exposed by live 0.10.454 testing while keeping the general evidence-reasoning architecture intact.

- Common overnight wording now shares the same deterministic semantic window as `last night`: `during the night`, `overnight`, and `through the night` resolve to the auditable 18:00-08:00 Hubitat-local window.
- History ambiguity prose uses an explicit `or` delimiter, so two alternatives such as `Hallway Light 1` and `Hallway Light 2` remain two selectable clarification choices rather than one combined button.
- WebUI clarification buttons preserve the original non-control question and append the exact selected device. Historical qualifiers therefore survive the clarification round instead of collapsing into a bare device-name request.
- The `/api/ask` serialization boundary now corrects a narrow class of contradictory `no data`/`no history` claims when current-turn deterministic history evidence for that exact named device proves one or more active intervals.
- A request-local aggregate fallback policy remembers complete, non-empty canonical `power`/`energy` aggregate results. Later model attempts to retry the same request through generic `value` or `valueStr` are skipped before they can force a full detailed inventory read. Generic fallbacks remain available when the canonical query returned no usable rows.

## Live issues addressed

0.10.454 live testing demonstrated the intended bounded reasoning behavior, but also exposed three concrete gaps: a two-light ambiguity was serialized as one combined choice; the clarification follow-up lost `during the night` and then made a false `no recorded data` claim despite a successful second history proof; and a top-power query discarded a valid `hubitat://context` result and spent about 30 seconds on a generic-value full inventory fallback before ending without an answer. This release closes those paths without adding a new question-specific router.

## Compatibility

Mutation, confirmation, device-command verification, and the existing 3-round/8-read reasoning budget are unchanged. The generic `value`/`valueStr` aggregate path is only suppressed after a complete non-empty canonical meter aggregate has already been obtained in the same request.