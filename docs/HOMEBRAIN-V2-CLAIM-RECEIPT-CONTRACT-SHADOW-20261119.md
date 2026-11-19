# V2 typed claim/receipt contract — shadow foundation

## Why

The alpha.150 prospective cohort scored 85% grounded factual claims, 30%
useful first answers, one unsupported definitive causal claim and 70% relevant
source sufficiency. Failures crossed arithmetic, source selection, empty-result
coverage, device health and fallback preservation. Another prose phrase list is
not an adequate response.

## Shadow contract

This milestone adds a bounded typed evidence packet to private Technical JSON.
Each original successful executed receipt receives a stable receipt ID. Safe
current-state, event, command, hub-info and grouped-log observations receive
stable fact IDs, along with the exact requested scope and explicit coverage
limits. Empty event/log results never become absence, continuous history or
complete-window proof. Failed and nonexecuted calls cannot create facts.

No claim binding is accepted yet. The packet explicitly reports
`claim_binding_status=not_supplied_by_current_runtime`, `enforced=false` and
`answer_changed=false`. It is a substrate for measured shadow work, not a new
publication gate.

## Boundaries

- No model prompt or model round changes.
- No new MCP call, source selection or retry.
- No answer rewrite or fallback change.
- No native write, approval, V1 or scheduler change.
- Original receipts remain authoritative.
- Labels, log messages and log-source names are not copied into the packet.

## Next measured step

Replay fixed private cohorts offline and compare human claim findings with the
typed facts/coverage limits. Only after a separate design review should a model
or deterministic renderer be allowed to submit explicit claim-to-fact bindings.
Enforcement requires a new prospective cohort; shadow telemetry alone is not a
quality improvement.
