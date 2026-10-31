# Stage 4I — Host-owned atomic proof obligations (offline only)

Source version **v0.18.289**, based on merged v0.18.288.

## Architectural decision after Stage 4H

GitHub-hosted actual Qwen2.5 3B and Llama 3.2 3B reviews of
eight independently curated complete synthetic answers returned
**one unsupported complete answer accepted by BOTH reviewers**,
plus **three of four adequate answers rejected by unanimity**.
Both reviewers were structurally valid. Therefore reviewer consensus
is insufficient as an answer-publication safety gate.

Stage 4I introduces explicit, source-grounded **atomic proof
obligations** outside natural-language model judgments.

A host-produced Stage 4A evidence packet contains bounded event roles
(command issued, state reported, input reported, coverage gap),
recorded clock basis, issuer app ID and known source limitations.
An offline candidate proposes typed atomic statements about these
facts; a pure host validator checks exact fields, role and source
witnesses. **It does not use a lexicon of trigger words or
hardcoded room descriptions.**

## Allowed atom types

- `recorded_event`: a source record with exact kind, entity ID,
  attribute and value. A command is *not* a reported state or
  physical effect.
- `recorded_issuer`: source has an explicit nonempty
  `issuer_app_id` matching the claimed immediate issuer. This
  does not identify the upstream sensor, human or automation decision.
- `recorded_clock`: the source record contains the exact
  timestamp and clock-basis combination claimed; a collector-received
  timestamp cannot be relabelled as independently source timed.
- `recorded_gap`: an explicit coverage limit matches exact
  subject/gap count/truncation, establishing incompleteness.
- `packet_limit`: source host packet expressly declares
  physical acknowledgement not proven, root cause not proven,
  history incomplete or absence claims not authorised. Those
  statements concern **evidence limits**, not confirmed physical
  inactivity or the absence of a command.
- `physical_effect`, `upstream_cause`,
  `absence_of_event`, `complete_history`: always **unproven**
  from the current Stage 4A packet. It has no certified source
  physical-ack proof, authenticated causal relationship, bounded
  complete negative history or completeness guarantee. Two real
  events occurring near each other still do not establish causation.

An unproven claim is **not a confirmed false statement**. It means
the *supplied evidence* cannot establish the proposition.

## Separation of truth sources and safety limits

The code verifies that a structured candidate claim is supported
by the **supplied host evidence fields**, not the model's own
assertion or an agreeing semantic reviewer. It fails closed on
unsupported claim types, unknown IDs, duplicate IDs, forged
physical ACK/causal/complete-history flags, invalid scope and
unexpected claim fields.

**The host must construct the packet from authorised canonical
receipts**. This standalone evaluator cannot cryptographically
authenticate a caller-provided packet. It can reject malformed
packets and false certainty flags but not a maliciously fabricated
yet correctly shaped packet.

Crucially, the evaluator **does not parse or attest the wording of
any authored sentence**. A model could submit a valid atomic
statement about a command while writing an unsupported causal
explanation. That gap must be solved before any active publication:
there must be a reliable, independently adjudicated mechanism
connecting every factual implication of actual prose to atomic
claims, including unstated or implied causality.

For that reason every result, including 100% host-proven atom
rates, returns:

- `claim_text_meaning_verified=false`
- `atomic_claim_extraction_from_prose_verified=false`
- `model_witness_attestation_is_not_truth=true`
- `publisher_approval=false`
- `active_answer_changed=false`

## Testing, privacy and scope

`stage4_atomic_proof_obligations.py` is pure offline Python.
It never calls an LLM, MCP, Hubitat, Home Assistant, network, or
filesystem; it has no active planner/publisher imports and no
device-control permissions. All reports expose only allowlisted
aggregate counts per atomic proposition, never entity IDs, real
timestamps, model-written text, or source excerpts.

The regression suite includes synthetic lighting, heating,
ventilation and contact/history witnesses, invented boiler ignition,
humidity/motion initiator, false source clocks, fabricated absence
and two-fact causal leaps. A separate curated static reference
benchmark uses prelabelled synthetic atoms; a perfect test score
is **not proof of real-world semantic accuracy** or independently
authenticated source truth.

No Ollama model invocation is needed to verify this deterministic
foundation. The existing Stage 4E–4H actual-model GitHub Actions
runs and their disappointing error rates remain unchanged.

## Next acceptance gates

1. Verify all existing GitHub release assurance, full Python tests,
   repository validation and smoke tests; merge only with all green.
2. Develop a separate, privacy-preserving sentence-to-atomic-claim
   completeness audit on *genuinely model-authored* text, including
   implied causes and material omitted explanations.
3. Obtain post-generation independently adjudicated labels of that
   authored text. Compare structured proof and model reviewer errors
   without giving model judges the reference labels.
4. If benchmarks improve, seek explicit owner approval before
   any live read-only shadow testing. Keep the current publisher
   authoritative until a separately approved reversible rollout.

Rollback: revert the source-only PR. No installed add-on update or
live Hubitat/HA changes are needed.
