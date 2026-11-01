# HomeBrainOS v0.18.306 — Stage 7.4: claim topic, epistemic position and evidence scope

**Synthetic-only evaluation. The production publisher, real home/device reads, MCP routing, models and automations remain unchanged.**

## Motivation

After Stage 7.3 the user's real Gemma Cloud **competing commands** review packet showed a clear and correct natural-language answer: the OFF report does not prove which of the two apps caused the light state. But Gemma assigned its fourth sentence the claim type \`unique_cause\` — a topic about *causal attribution*, not necessarily a positive assertion that a unique cause is established. The old checker treated all \`unique_cause\` labels as affirmative high-risk claims, regardless of the expressed negative/uncertain position.

A model saying "the evidence does **not establish** who caused this" is not the same as either "App A **caused** it" or "App A **did not cause** it." Conflating them creates misleading warnings and may drive brittle phrase-specific patches. We need typed epistemic meaning while preserving independent full-prose review.

## Additive Stage 7.4 changes

- The *experimental* final-answer prompt now requests \`homebrain-stage6-answer.v3\`: every sentence includes \`kind\` (topic), \`evidence_ids\`, \`atoms\` and a bounded \`epistemic:{position,scope}\` declaration.
- Position is **affirmed**, **refuted**, or **not_established**. Scope is **examined_records**, **supplied_records**, or **universal**. These are statements **authored by the model**, not facts proven by the system. A model-declared refutation is not automatically supported by a source that mentions the subject.
- The host checks the envelope, allowed enumerations and citations. It still independently validates exact field-value atoms, rejects fabricated IDs/oversized atom arrays and retains the existing command/state source structural checks.
- For \`unique_cause\`, \`physical_confirmation\` and \`absence_proven\`, **affirmative and categorical-refutation declarations** remain high-risk and unsupported by these fictional sources. \`not_established\` scoped to inspected/supplied evidence becomes a distinct **scoped unresolved model declaration**, not a proven causal statement. Universal unestablished claims are a separate warning category.
- A scoped unresolved declaration **does not make a high-risk sentence independently supported**: the original \`typed_source_supported\` remains false; provenance, physical effects and prose semantics are not certified by the model self-label. The UI displays the number of these declarations separately from high-risk affirmative/refutation positions, while still reporting unsupported typed source claims.
- Stage 7's independent reviewer packet preserves the original model text, cited evidence and declared position/scope, and explicitly defaults **“Does sentence meaning match its declared position/scope?”** to **Not reviewed**. A human reviewer must check alignment. Exporting the optional review never changes the active publisher.
- v1 and v2 schemas remain parseable for previous tests and offline regressions; they receive **no invented epistemic position**.

## Adversarial tests

Mock-only tests cover:
- \`unique_cause\` + \`not_established\` + \`examined_records\` clearly separated from an affirmative cause.
- Same topic labelled affirmed or categorically refuted remains high-risk.
- Universal scope that overreaches available evidence cannot be counted as scoped uncertainty.
- Contradiction attack: model **declares** \`not_established\` but **writes** “the Inactivity App definitely physically caused the OFF state.” This deliberately illustrates why machine-checked metadata is NOT full-prose certification.
- Unknown/extra/malformed declaration keys rejected; v1/v2 backward compatibility; no false source support inherited by refutations; no GitHub CI cloud inference; mock four-call Stage 6 path; never imports into production publisher/MCP executor.

## On-phone follow-up

Upgrade Hubitat MCP AI to **v0.18.306**. In the experimental Stage 6 synthetic panel, run **Two apps issue competing commands** once with explicit consent (up to four Ollama Cloud calls on the existing account). Look for the **Epistemic declarations** counts and sentence-level positions. Expand **Stage 7 · Independently review every sentence**, compare the actual wording to the self-declared position/scope and assess the original causal question separately in Stage 7.2.

Success is **not** merely a \`not_established\` label. The natural explanation should actually say that the reported OFF state cannot identify the unique responsible application, and that lack of observed physical acknowledgement does not prove physical nonexecution.

**This release does not automatically classify the meaning of free prose.** A well-formed declaration can be dishonest or inconsistent with a sentence; the reviewer must check. No live home investigation, no publisher activation, no extra/retried cloud inference, and no automatic rewrite of model-authored language.

Rollback: revert PR and restore v0.18.305.
