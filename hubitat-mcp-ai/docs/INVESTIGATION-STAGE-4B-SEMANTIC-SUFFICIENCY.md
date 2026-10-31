# Stage 4B — Independent semantic-sufficiency review protocol (offline)

Source version **v0.18.282**; base v0.18.281 Stage 4A.

## Goal

The active V3 publisher renders hardcoded bathroom-specific prose. Stage 4A
introduced domain-general, model-authored sentences with exact source-fact
citations and typed assertions, but **citation validity cannot prove sentence
truth**. For example, a genuine heater setpoint command cannot establish
that a boiler fired, a radiator valve opened, or a sensor caused heating.

Stage 4B provides a **semantic review protocol and a quality-measurement
harness**, not another rule-based phrase detector or an active replacement
publisher.

## Separation of duties

1. The existing Stage 4A typed check must pass first; otherwise the
   sentence never reaches semantic review.
2. `build_stage4_semantic_review_request(draft, packet)` isolates each
   model-authored sentence with **only its exact cited host-owned facts**,
   source role/clock information and general source-completeness caveats.
   No unconnected household evidence can be used to invent a cause.
3. Two externally submitted independent reviewer assessments (e.g., from
   separately invoked model reviewers in a future offline harness) choose
   exactly one of **entailed**, **contradicted**, or **insufficient** for
   every sentence. To claim entailment, a reviewer must declare all cited
   fact IDs were inspected. A sentence containing any unproved assertion
   is *insufficient* even if a component clause is correct.
4. `assess_stage4_semantic_sufficiency(..., reviewer_envelopes=...)`
   validates the complete, bounded review envelopes. It reports only
   reviewer **concordance**, disagreements, rejections, missing citations
   and malformed reviews. No free-text explanations or model prompts are
   copied to report output.
5. `benchmark_stage4_semantic_reviews(cases)` compares agreed reviewer
   assessments with **separately authored expected semantic judgments**.
   It computes false acceptance and false rejection rates, with unknown
   labels rejected. Expected labels are never passed to the reviewers.

Stage 4B does **not** actually invoke an LLM or an independent judge yet.
The supplied reviewer envelopes in regression tests are **constructed**,
not observed model judgments. Their agreement is not proof of semantic
entailment or independence. Benchmark labels are separately authored test
references, not authenticated production truth.

**The public safety gate ALWAYS stays closed**: even with valid typed
claims and two agreed positive reviewer reports, the result keeps
`independent_semantic_truth_verified=false`,
`production_publication_approved=false`,
`active_answer_changed=false`. No live model prose is published.

## Core semantics / cross-domain adversarial examples

The 14-case regression corpus includes 7 plausible source-grounded
statements and 7 counterfactual, unsupported statements across 6 domains:

- Lighting: recorded level command vs invented motion initiator.
- Heating: setpoint request vs unverified boiler ignition and radiator actuation.
- Ventilation: fan OFF command vs assumed humidity-triggered decision.
- Power: commanded ON vs physical electrical consumption.
- Sensors: source humidity time vs relabelling source time as collection time.
- History: collector-received contact vs independent device source time;
  recorded historical gap vs fictitious complete absence of commands.

Supported and unsupported sentences can use *identical typed claims and
citations*. There is no hardcoded room name, phrase regex or confidence
score threshold masquerading as general-language semantic reasoning.

The test set also deliberately makes both mock reviewers approve a false
physical-causation sentence. The benchmark **must** count it as a false
acceptance, even though the review protocol reports reviewer concordance.
A false rejection of a useful sentence is measured separately.

## Privacy, performance and scope

- Up to 16 sentences and 4 cited facts per sentence, from already bounded
  Stage 4A packets. Reviews cannot introduce new fact IDs, new fields or
  claims about uncited entities.
- Reports consist only of allowlisted verdict counts/reason codes and
  aggregate benchmark metrics; no model-authored text, device IDs, personal
  names, exact timestamps, tool arguments, tokens or source excerpts.
- The review request deliberately contains the user's original sentence
  and cited evidence; it is **not a shareable privacy-redacted export**.
  Keep it local until an independently approved reviewer connection,
  retention policy, and access boundary are available.
- No new model calls, evidence reads, network calls, device controls,
  migrations, feature flags or production agent/publisher imports. Stage 3F
  local capture remains OFF in the installed add-on.

## Next required gates

- Stage 4C: run **actual independently operated** semantic reviewers
  offline over redacted, adjudicated test cases. Measure disagreement,
  false-acceptance by domain, useful-answer preservation, clock/issuer
  confusions and performance without assuming judge independence.
- Expand benchmark using genuinely observed, separately checked incident
  traces from opt-in supervision; constructed cases cannot certify real
  field behaviour.
- Stage 4D: only after acceptable quality, explicit user approval, and a
  kill switch, propose a reversible shadow *comparison* with the existing
  published answers; do not silently replace those answers.
- Production answer changes remain separately gated by factual-fidelity
  regression, explicit rollback, and a supervised read-only rollout.

Rollback: revert the additive Stage 4B source-only PR. No live add-on
update or household change is necessary.
