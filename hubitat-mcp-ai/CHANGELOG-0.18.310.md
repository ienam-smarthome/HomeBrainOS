# HomeBrainOS v0.18.310 — Stage 7.8: follow-up evidence sufficiency

**Synthetic-only Stage 6/7 experimental investigation and independent review.** This release does not modify production publisher, normal model routing, MCP/Hubitat/Home Assistant device access, automations, or Cloud account settings. No extra provider requests or retries are introduced.

## Motivation

Three real Gemma Cloud scenario runs exposed a recurring problem: matching individual source facts and selecting relevant evidence do not guarantee a correct *inference* about what additional evidence could prove. On v0.18.309, Gemma correctly retrieved the MQTT broker status, last genuine device telemetry and OFF command, but proposed inspecting S4's periodic watchdog heartbeat **to determine the exact moment** connectivity was lost or detected. The tick is `actual_plug_packet=false`; alone it does not establish that moment. Similar limitations apply when a device packet is used to assign command causation or when source-event timestamps are treated as proof that clocks were synchronised.

## Implementation

- Existing v3 `homebrain-stage6-answer.v3` optionally accepts `next_evidence_assessment` with exact bounded keys: `proposal_kind`, `could_establish`, `cannot_establish`, `additional_proof_needed`. The model must state **what a proposed source can show, what it cannot show alone, and what additional evidence is required**. A precise allowlist of source-class names prevents fabricated class keys. No model-authored declaration is automatically accepted as true.
- Existing v1/v2 and earlier v3 answers without the optional assessment remain valid. Missing declarations are explicitly **not reviewed**, never deemed successful. Unexpected or malformed extra fields fail closed; existing citation/atomic-value safeguards remain intact.
- New `stage78_followup_sufficiency.py` projects generic type-level limitations of **examined fictional records** only (broker transport vs device, watchdog ticks vs loss instant, telemetry vs command causation and clock accuracy, issued commands vs physical execution, state reports vs acknowledgements). This is a reference for humans, not a source-dependent natural-language classifier or an automatic entailment validator.
- Mobile Stage 7.8 collapsible review shows the model's proposal, its four declarations, generic source capability boundaries, and links reviewers conceptually to the existing independent next-evidence quality control. No new rating forms or additional Cloud calls.
- Synthetic/adversarial tests include the actual watchdog overclaim, manufactured model declarations that contradict capabilities, malformed and legacy output, all three synthetic scenarios, mobile output, full four-call mocked pipeline and no production module import.

## What this does NOT establish

The model can still self-label an overconfident next-evidence proposal with plausible limitations. Source-type checks are not semantic review and cannot determine all meanings of a sentence; human review is still required. The hidden reference sources never control model read choices. No `publisher_approval` is granted.

## Acceptance test from phone

Install **v0.18.310** and repeat **Stage 6 → Mesh plug: connected broker, offline device** with explicit consent (up to four existing Cloud requests). Verify the natural-language suggestion no longer treats one watchdog tick as proof of the precise loss time. Under Stage 7, inspect **Stage 7.8 · Can suggested evidence actually prove the claim?** and compare `could_establish`, `cannot_establish`, and `additional_proof_needed` to the genuine fictional records. Check the next-evidence quality human dropdown and send the review packet.

Rollback: revert the Stage 7.8 PR and restore v0.18.309.
