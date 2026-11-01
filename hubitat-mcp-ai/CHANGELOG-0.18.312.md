# HomeBrainOS v0.18.312 — Stage 7.9: Declared proof target and evidence capabilities

**Synthetic Stage 6/7 only.** Does not modify the real assistant's production publisher, MCP routing, Hubitat, Home Assistant, automations, local/Cloud credentials or request budgets.

## Why

The v0.18.311 live Gemma Cloud MQTT fixture correctly selected all three reference-relevant sources, distinguished broker and physical plug status, and withheld unwarranted OFF-causation certainty. But its follow-up suggested that S4's single periodic watchdog heartbeat could establish the **exact** moment the heartbeat ceased, while the model's separate structured assessment described only an **approximate** driver-signal time. Neither is independently proven by the S4 record (one watchdog_tick, actual_plug_packet=false).

Stage 7.8 already exposed general source-class limitations but could not compare a source's declared role with the intended conclusion. Stage 7.9 adds a bounded structured comparison while leaving full natural-language meaning to a human reviewer.

## Changes

- Optional v3 `next_evidence_assessment.proof_target` using nine enumerated types: `reported_device_state`, `broker_transport_status`, `watchdog_detection_window`, `exact_connectivity_loss_instant`, `physical_actuation`, `specific_command_caused_outcome`, `source_clock_accuracy`, `controller_decision`, `other`. The existing proposal kind and could/cannot/proof-needed fields remain; legacy model outputs without a target are accepted as **not declared**.
- Experimental model prompt asks it to select the actual intended proof target, including stronger claims implied by its free-text suggestion, even if insufficient. This is **model-authored**, not an evaluator decision or oracle.
- New `stage79_proof_target_review.py` checks a generic evidence-class/target compatibility table **only after** all inference is complete. `watchdog_history` can potentially bound a detection **window** with continuous coverage but cannot alone prove the exact physical loss instant. Device telemetry may observe state, not command origin. A command execution receipt can be relevant to actuation or attribution only when independently authenticated and properly linked; type matching is NEVER proof.
- Stage 7 packet and mobile reviewer display the comparison with explicit warnings that a model may under-declare the target while its actual prose makes a stronger claim. The existing human Next evidence quality review is still required; no automatic semantic certification or publication.
- Malformed optional target values are withheld under the v0.18.311 recovery policy; factual assertions and source citations remain strictly validated.

## Tests and safety

Adversarial tests include exact-vs-window watchdog claims, stale telemetry vs initiator attribution, broker vs device status, command issuance vs physical execution, authenticated clock bounds, malicious prose with a weaker declared target, malformed target fallback, legacy v3 acceptance, all three fictional scenarios, four mocked Ollama requests, unchanged production modules, and UI clarity.

**Limitations:** This is a structural finding only. It is not a semantic judge of what the free-text suggestion *actually* says. Host-declared consistency flags can be bypassed by a model declaring a weaker target. Independent human review is required. A matching class is evidence relevance, not sufficient real-world proof.

After installing v0.18.312, rerun **Stage 6 → Mesh plug: connected broker, offline device** and inspect Stage 7.9. No live device calls. Rollback: revert this PR and restore v0.18.311.
