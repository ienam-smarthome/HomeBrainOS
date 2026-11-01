# HomeBrainOS v0.18.309 — Stage 7.7 relationship reasoning and coverage

**Synthetic-only adaptive investigation and independent human review.** No production publisher, normal assistant orchestration, MCP commands, Home Assistant/Hubitat reads or device changes. Existing consent and up-to-four Ollama Cloud requests remain unchanged; all GitHub tests use mocks.

## Real-model motivation

The user's v0.18.308 Gemma Cloud results from all three fictional Stage 6 scenarios showed a repeatable distinction between accurate source-value matching and full investigative reasoning:

- **Competing commands:** 3/3 host-observable evidence types and correctly scoped unresolved unique cause, despite model choosing 2/3 finding labels.
- **Clock conflict:** all reference sources inspected, correct individual timestamp values, but Gemini failed to explicitly contrast OFF→ON source-time order with ON→OFF collector receipt order. Correctness of origin timestamps does not establish clocks are synchronised or physical state transition order.
- **Stale connectivity:** 2/3 relevant sources inspected and 3/4 observable types; model selected watchdog heartbeat S4 over broker session S1 and omitted the core distinction between driver-to-broker connectivity and genuine plug connectivity. Real device-packet origin is not a guarantee its clock is accurate.

## Changes

- Experimental source-selection prompt explicitly gives the **selected user-visible scenario title** alongside the original question in planning and final explanation requests. This is not the hidden benchmark rubric. The model is encouraged to prioritise direct evidence for distinct unresolved contrasts over redundant/proxy status evidence. The model still chooses each next read; the host never substitutes a hidden gold source or exceeds the existing three source-read/four inference-call budget.
- Final experimental explanation prompt asks Gemma to compare source-time order and receipt-time order when comparable fields are available, and to distinguish device packet provenance from authenticated clock synchronisation, with no hardcoded fixture answer text.
- New isolated `stage77_relationship_review.py` evaluates postrun **observed, same-device, same-source-clock-basis** source/receipt inversions; explicitly does not prove physical event order, correct clocks or a complete history. It separately identifies broker-session, watchdog tick and independent device packet record IDs. Unread evidence required by a **critical host-held reference obligation** is revealed only after inference and is never a control signal to the planner.
- Mobile independent Stage 7 reviewer shows clock inversions and postrun critical reference gaps without claiming automatic semantic certification. Existing human review controls remain unchanged.

## Regression coverage and boundaries

Mock and source-only tests cover exact E2/E3 reversal, E1 broker gap when S4 is chosen, no gap when S1 is chosen, missing/duplicate/unknown source selections, dishonest authored prose, four-call budget, hidden-reference isolation, UI and production publisher isolation. Existing 7.1–7.6 tests remain in the full CI matrix.

**A correct structured relation does NOT mean Gemma explained it correctly.** The reviewer must check model-authored sentences and whether each part of the original question was answered. This release makes the omissions measurable and aims to improve planning, but requires new live Ollama Cloud acceptance tests. No production publisher activation.

Rollback: revert Stage 7.7 PR and restore v0.18.308.
