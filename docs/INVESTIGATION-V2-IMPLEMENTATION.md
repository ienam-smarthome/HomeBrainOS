# Investigation V2 — evidence foundation (first implementation)

This package implements the first **passive** portion of RFC-INVESTIGATION-V2.md.
It has no runtime invocation from the current orchestration and does not issue
MCP calls or change devices, apps, rules, permissions or confirmation workflows.

## Current contract

`build_case_file(original_question, receipts)` converts recognized successful
Hubitat device-event and app-log receipts into a request-scoped, UTC-ordered
`CaseFile`. The typed records preserve the original timestamp/offset, action,
producer ID *only when explicitly supplied by the event's producedBy field*,
device target, provenance pointers and epistemic stage.

A command-issued event is **not** a reported switch transition or independently
observed physical state. An app log statement is not itself proof of command
dispatch. The `triggered` listener list does not establish command producers.

Coverage independently records the query filters, oldest/newest retrieved
instants, source integrity, truncation, page reach and source completeness.
Neither successful pagination nor a large `hoursBack` proves completeness.
Unknown or malformed receipts cannot create typed incident facts.

Unknown source shapes remain coverage-only until reviewed adapters are added.
No output validator, model planner or new causal inference is implemented yet.

## Tests

`python -m pytest -q tests/test_investigation_v2_evidence.py`

The golden fixture is a **sanitized representative extract from the RFC**, not
a recording of the entire event stream or a complete physical-state history.
It preserves all six command events and two level reports; it checks the
off command at 00:41 remains visible without falsely proving physical OFF.
Other tests cover conflicting device IDs, empty reads, log-versus-command
semantics, double-source deduplication, generic MQTT/temperature events and
offset-aware ordering across the UK DST fallback.

## Next development boundary

1. Add explicit reviewed adapters for configuration snapshots, app execution
   receipts and transport acknowledgement with event-time versus current-time
   distinction and safe source references.
2. Build hypothesis/discriminator and planner contracts against this case file,
   leaving host MCP tool authorization and write confirmation untouched.
3. Add non-destructive atomic-claim/omission evaluation and V1/V2 replay
   comparison. Wire **read-only shadow mode first**, then cut over only after
   tests establish source fidelity and usefulness across unrelated incidents.

Do not wire the package into the production answer pipeline or claim a runtime
reasoning improvement from these unit tests alone.
