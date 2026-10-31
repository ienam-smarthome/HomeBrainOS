# Hubitat MCP AI v0.18.275 — Stage 3A autonomous read selection foundation

This is a shadow-only **source release**, not an instruction to install the add-on.

Adds `stage3_evidence_frontier.py` as an offline validator and ranker for
model-proposed, bounded read-only MCP candidates, reusing the existing
`causal_source_feasibility.py` and Stage 2 canonical evidence interfaces.

It accepts only currently catalog-present read leaves with independently
source-attested device/app IDs and validated bounded arguments. Repeated exact
operations are suppressed whether succeeded or failed; a new bounded scope
can still be proposed. Candidate scoring is not an assertion of causation.
No arbitrary five-call investigation limit is imposed by this module.

Regression tests span historical lighting, app issuers versus listeners,
duplicate and failed reads, forged scope and secret handling, 20+ unique
model-proposed options, and heating command data.

**NOT ACTIVATED:** No agent/model tool-loop imports, MCP calls, new
permissions, new HTTP endpoints, runtime routing or answer publisher
changes, HA/Hubitat writes, installation, config switches or migrations.
The installed v0.18.274 (or older) need not be upgraded for this shadow stage.

Detailed boundaries and the Stage 3B/3C gates:
`docs/INVESTIGATION-STAGE-3A-EVIDENCE-FRONTIER.md`.

Rollback: revert this additive branch; no running component to restore.
