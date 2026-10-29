# Hubitat MCP AI v0.18.225 — Evidence-first command chronology in Native V2

## Reason for this stage

The 29 October Bedroom 3 Mesh live trace had two independently attested facts:

- A device metadata read reported lastSeen=Mon Oct 12 01:30:01 BST 2026, healthStatus=offline and mqttStatus=connected.
- A separately device-scoped event read attested that power-saving app 3950 issued an OFF command at 2026-10-12T01:30:01.743+0100, with later ON commands from other apps.

V2 only reported command counts and omitted the exact **0.743-second proximity**, which is materially relevant to an investigation. The missing piece is a generic, source-bounded chronological relationship, not an entity-name routing patch or an unsupported assertion that a rule caused the physical device failure.

## Architecture change

- Introduce a shared, bounded, read-only temporal-lead interpreter for *any* uniquely verified target device. It requires matching, approved device-detail and scoped event-history receipts and source-attested producing app IDs.
- Parse only explicit UTC offsets, Z, or explicitly labelled BST/GMT; refuse ambiguous naive timestamps. The autumn clock change stays zone-disambiguated.
- Compare independently sourced lastSeen/lastContact/lastMessage against actual command sample instants. Select only a command within a **three-second** bounded window, report its source read IDs and absolute temporal gap. No correlation is fabricated when sources cannot be aligned.
- Present the candidate as a source-backed *investigation lead*, never proof of command delivery, power loss, device communication, historical coverage, or final cause. Surface subsequent ON commands without implying successful recovery.
- Return the lead to the planning model in the ordinary guarded READ transcript, with an optional follow-up to inspect the attested app's configuration. The model retains control of which READs to request; the host never automatically makes extra calls.
- If a unique device has no source-authoritative warning incident and the model cannot produce validated narrative, the user sees a direct, concise, independently proven **timing observation**, including causal limits and next safe checks.
- Distinguish displayed host-verified chronology from unused model claim-selection diagnostics, as with room answers.
- Keep production Main Ask, write controls, device actions, source protections and room handling unchanged.

## Regression evaluation

`pytest -q tests/test_investigation_v2_temporal_lead_0_18_225.py`

Replay includes lastSeen at 01:30:01 BST, app 3950 OFF at 01:30:01.743+0100, later app-issued ON instructions, MQTT broker status, timezone fall-back disambiguation, unrelated IDs, wrong scope, absent metadata, distant events, repeated event pages, and malicious model assertion of a verified physical cause.

## Read-only live question

> Investigate why Bedroom 3 Mesh stopped communicating around 12 October 2026. Correlate its device-reported lastSeen with exact timestamped commands from separately scoped event history, and inspect the responsible app's current configuration if independently available. Explain what is verified, what is only a hypothesis, and what evidence would discriminate causes. Do not change anything.

Success means a short answer that highlights the independently timestamped OFF-command proximity, distinguishes later ON instructions from confirmed delivery, and explicitly states that actual power loss and causal mechanism remain unverified. It should not describe the driver's MQTT broker connection as proof of the plug being online.

## Limits

Temporal proximity is not physical causation. Model-selected access to the issuing app, full event history, rule execution and physical connectivity may be missing or unavailable. This is a focused general chronological evidence enhancement, not the final multi-step autonomous reasoning architecture or proof of Claude parity. Promote to production only after separate comprehensive live validation.
