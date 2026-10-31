# Hubitat MCP AI v0.18.273 — Investigation foundations (shadow only)

## Stage 1: locked-down incident regression baseline

Reuses the existing anonymised five-cycle lighting fixture from 30 October
2026. Asserts the existing publisher continues to report the complete paired
source-timestamped cycle timeline and clearly state that the initiating ON
command is unverified. Journal collector reception and source timestamps stay
distinct, as do app-notified listeners and direct command issuers.

## Stage 2: canonical evidence and verified identity foundation

Introduces canonical_investigation_evidence.py, an additive read-only
adapter over existing evidence receipts. The module exposes immutable,
source-tagged VerifiedIdentity, CanonicalEvent and EvidenceCoverage records
and a CanonicalEvidenceView. Scoped Hubitat device/app names can survive
into typed projections; app listener notifications cannot be promoted to
command issuers. Clock basis, journal coverage gaps, truncation, timestamp
integrity and physical acknowledgement uncertainty remain explicit.

New tests cover five recovered lighting cycles; strict ID-to-name matching;
app command attribution versus event subscribers; forged/unsafe names,
conflicting identities, wrong-device source rows, missing timezone offsets,
gap-bearing history, and non-light device attributes.

**Not activated:** No runtime integration or new publisher; no changed tool
selection, Ollama model prompts, Hubitat commands, Home Assistant
configuration, live automation, database, or network connection.
This is versioned due to repository validation policy. Performance and answer
style should be identical to v0.18.272 until a later separately reviewed
activation PR. See docs/INVESTIGATION-FOUNDATION-STAGES-1-2.md.

Rollback: revert the additive module, tests and documentation. No live system
migration to reverse.
