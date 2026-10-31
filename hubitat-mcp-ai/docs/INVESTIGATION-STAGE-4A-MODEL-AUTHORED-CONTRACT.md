# Stage 4A — Model-authored narrative contract (offline shadow foundation)

Source version **v0.18.281** from merged main **v0.18.280**.

## Why Stage 4 must be architectural

The existing `causal_claim_publication.py` V3 renderer checks a structured
claim envelope, but then publishes a deterministic, bathroom-specific
lighting narrative. That implementation supports a narrow incident and
cannot serve as a natural, general-purpose Hubitat/HA explanation engine.

Stage 4A creates a **new independent evidence-to-prose interface** without
using the old bathroom prose or replacing the active publisher.

## Source packet

`stage4_narrative_contract.build_stage4_evidence_packet(receipts)`
reuses Stage 2's **canonical source evidence view**. It can emit up to 80
stable, host-issued fact IDs with independently scoped records of:

- reported states and input observations;
- issued Hubitat commands with verified immediate app issuer ID when
  directly represented in a native source event;
- source event time and collector reception time, distinctly typed;
- explicit coverage gaps and truncation, never interpreted as absent events.

Verified device/app labels are drawn only from the canonical view's scoped
identity rules; conflicting identities are omitted. Event observations
are not physical acknowledgements. Native command issuers do not prove
what triggered the app; notification subscribers are not issuers.
A missing or empty history is **not** evidence that no command was issued.

The packet carries explicit partial/omitted-fact counts, never claims a
complete historical record or a verified upstream cause, and contains no
tool executor or network access.

## Model authoring protocol

The model is free to choose what matters, sentence ordering and natural
wording. It returns a versioned candidate:

```json
{
  "schema": "homebrain-stage4-draft.v1",
  "sections": [
    {
      "name": "evidence",
      "sentences": [
        {
          "text": "A controller command was recorded in the device history.",
          "citations": ["f001"],
          "claims": [
            {
              "fact_id": "f001",
              "kind": "issued_command",
              "entity_id": "101",
              "attribute": "setLevel",
              "value": "setLevel",
              "clock_basis": "source-reported",
              "time_utc": "2026-10-30T14:50:37.911000+00:00",
              "issuer_app_id": "3001",
              "physical_ack_verified": false
            }
          ]
        }
      ]
    }
  ]
}
```

The JSON above is **illustrative only**; the exact assertion must be copied
from a real host-issued fact and must match that fact in the same packet.
Never synthesize app IDs, proof roles or event clocks from a text prompt.

The model's citation+claim arrays must be complete and exact for each
factual sentence, with no extra unknown attributes, unsupported roles,
issuer substitutions, event clock upgrades, or physical ACK assertions.

## Critical separation: structured claims versus prose truth

`validate_stage4_model_draft(candidate, source_packet)` checks the typed
claims for exact fact references and source attributes. It returns only
bounded verdict counts and allowlisted failure reasons; it never publishes
or returns the model's natural-language text.

**Structured attestation is not semantic prose validation.** A sentence
like "This proves the motion detector physically opened the fan" can still
carry a valid citation to a later fan command. The typed claim may pass,
but the sentence's causal conclusion is unjustified. Stage 4A explicitly
returns:

- `prose_semantically_verified: false`
- `safe_to_replace_existing_answer: false`
- `published: false`

**Always**, even when every typed citation is valid. This is fail-closed
and deliberate. No keyword list or domain-specific suppression template
is presented as a universal semantic verifier.

The model-authoring instruction is a domain-general proposal prompt; no
production prompt, model-loop import, caller, HTTP route or final-answer
pipeline has been changed. The existing V3 publication and legacy
fallback remain untouched.

## Regression scope

Cross-domain (light, thermostat, extractor, power and contact/humidity)
source command/state examples; five-cycle source journal truncation;
consumer notification not promoted to app issuer; spoofed entity, value,
clock, command or physical ACK; fabricated missing-event inference;
citation mismatch/unknown witnesses; model hallucination with valid typed
citation; input immutability and active-code import prohibition.

## Further gates

1. Full repository CI must pass at exact PR head. Merge only if green.
2. Stage 4B must add an independent **sentence-level semantic sufficiency
   mechanism** evaluated against diverse genuine data and adversarial
   paraphrases—not lexical keyword patches. Validate factual and causal
   relationships, clock semantics and unknown coverage; measure false
   acceptance and preservation of useful explanations.
3. Stage 4C may introduce a separately opt-in, reversible shadow comparison
   against the currently published answer, with no tool writes.
4. **Do not publish model-authored prose** until stage 4B/4C show
   satisfactory safety/quality and a separate rollout is approved.
5. Genuine Stage 3F trace capture remains disabled in the add-on and requires
   separately approved supervised instrumentation.

Rollback: revert this additive source-only PR; no installed live state,
configuration, device or publisher has changed.
