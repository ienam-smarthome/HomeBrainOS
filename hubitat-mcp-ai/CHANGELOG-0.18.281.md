# Hubitat MCP AI v0.18.281 — Stage 4A model-authored evidence contract

**Source-only; not a publisher activation or live installation.**

- Adds `stage4_narrative_contract.py`: builds a bounded, domain-neutral
  source-fact packet from Stage 2 canonical evidence, retaining actual
  source-vs-collection clock basis, command issuer boundaries and history
  gaps, without bathroom-specific hardcoded publication.
- Defines a model-authored JSON answer envelope with prose sentences and
  explicit evidence fact IDs and typed assertions.
- Checks every typed assertion against independently scoped, host-owned
  witnesses; rejects fabricated facts, altered device IDs, values, clocks,
  issuer attribution, physical acknowledgement and missing citations.
- Explicitly does **not** semantically validate the free-text sentence.
  `prose_semantically_verified`, `published` and
  `safe_to_replace_existing_answer` always remain FALSE, even for perfect
  typed claims; unsupported causal prose is not approved by citations.
- Adds multi-domain and adversarial regression scenarios and full source
  documentation of the Stage 4B/4C evidence/semantics gates.

No new model calls, MCP execution, input-routing, device controls, prompts
in the active orchestrator, legacy publisher modifications, Home Assistant
or Hubitat changes, rollout flags, telemetry storage or migrations.
Stage 3F local capture remains disabled by default.

See `docs/INVESTIGATION-STAGE-4A-MODEL-AUTHORED-CONTRACT.md`.
Rollback: revert this additive PR. No live migration or update is required.
