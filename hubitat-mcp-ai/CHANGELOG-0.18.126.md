# HomeBrainOS 0.18.126 — Investigation V2 Phase D atomic claim verification

## Added

- Atomic, source-backed observation claim contract: exact matching by
  canonical record ID, epistemic stage, action, value, device target,
  producer ID, absolute UTC instant and time basis.
- Source-backed, explicitly **unverified** hypothesis claims, rather than
  silently promoting model-suggested explanations into known root causes.
- A single bounded model revision step for **rejected claim IDs only**.
  Previously accepted claims remain immutable and material command
  chronology is always retained by the case-file renderer.
- Read-only opt-in `enable_atomic_claim_validation=True` on the existing
  Investigation V2 evaluation harness. Defaults remain unchanged.
- Unit and replay coverage for falsely promoting issued OFF to reported OFF,
  wrong app producers, conflicting source times, invented records, unsafe
  extra prose, duplicates, attempted rewrite of an approved claim,
  malicious tool calls, failed repairs and unrelated MQTT device events.

## Restrictions

The host produces supported observations directly from canonical source
records; the LLM cannot certify unbounded prose as factual. Models may
select source records and nominate tentative explanations; unsupported
claims remain rejected and are never substituted for independently
verified history.

Investigation V2 remains an explicit evaluation harness, NOT the default
HomeBrain chat answer, nor a background MCP reader or write path. Full
natural-language causal synthesis, shadow comparison and production
migration remain gated future stages. Existing confirmation and writes
are untouched.
