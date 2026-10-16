---
name: hubitat-investigator
description: Evidence-led, read-only causal investigation of Hubitat device, automation, bridge and integration incidents.
---

# Hubitat Investigator

## Purpose
Investigate **why** a device changed, failed to change, or behaved unexpectedly. Do not stop at the first preceding command, the last state event, or a generic "external controller" explanation. This skill is a *method*, not a new privileged tool or a replacement for host-owned evidence validation.

## Safety and authority
- Investigation is read-only. Never call a write-capable tool as a diagnostic step. Existing confirmation, authorization and post-write verification policies remain authoritative.
- Device IDs, app IDs, timestamps, event producers, configuration and actual tool availability must come from the host and **current request's evidence**. Prior chat/memory is a lead, never live proof.
- Preserve source receipts, coverage (including truncation/caps), source clocks/timezone, and confidence. Do not invent historical coverage when the tool returns zero records.
- Never include passwords, MQTT credentials, API keys, URLs containing tokens or sensitive settings in the answer, model prompt, trace or test fixture. Redact at collection boundaries, flag detected leakage, and recommend scoped credential rotation if confirmed exposed.
- A Hubitat log describing a command is evidence of a command/report, not proof the physical lamp responded or that a particular controller caused its state.
- Missing log evidence is not evidence of absence without demonstrated stream scope, retention and completeness.
- Obey existing host tool/deadline/concurrency budgets; when exhausted, give the best supported partial conclusion and exact next discriminating check.

## Investigation workflow

### 1. Define the incident
Resolve the subject, device identity, requested time/window, event/state transition, expected behaviour, and the user's question. Preserve ambiguity explicitly. Distinguish device state, command sent, physical observation and integration report.

### 2. Discover causal topology
Build an incident-scoped graph (not whole-hub enumeration by default):
- Target device and parent integration/bridge (e.g. Hue, Zigbee, MQTT, Matter).
- Configured controlling rules/apps, enabled state, triggers, conditions, restrictions and action targets.
- Allowed motion/contact/illuminance sensors, button controls, app-to-app handoffs and external command paths.
Mark each edge **configured**, **observed**, **inferred**, or **unverified** with its source. An enabled rule alone does not prove execution.

### 3. Reconstruct a multi-stream timeline
Read relevant bounded events/logs around the focal time, expanding only where evidence justifies it. Include preceding transitions (especially OFF), commands, actuation acknowledgements, reported states, mode and trigger changes. Normalize times only when source timezone is known; preserve original timestamps and precision. Group distinct streams by provenance, and separate timestamps from receipt/order assumptions. Note completeness, retention, pagination, capped results and possible clock skew.

### 4. Spot anomalies and unexplained gaps
Ask: Was an OFF event immediately before an ON? Is the command-to-report lag unusual relative to comparable *measured* prior occurrences? Are sensors silent or missing due to source gaps? Did another controller act between command and observation? Is the apparent state a bridge resync or retained/replayed MQTT message? Do not label delay as anomalous without a verified baseline.

### 5. Generate competing hypotheses
Consider at least two materially distinct explanations when available (e.g. automation command, direct bridge/button action, state synchronisation, cross-integration feedback). For each, record:
- Positive evidence and source IDs.
- Counterevidence and contradictions.
- Required assumptions.
- Missing decisive evidence.
- Coverage limitations.
Rank by ability to explain the **whole sequence**, not just temporal proximity or producer familiarity. A leading recorded command source is not confirmed physical causation.

### 6. Select next evidence by discriminating value
Seek the smallest read-only query that separates the top hypotheses. Examples: origin-bearing MQTT receive/subscribe logs, SenseCap command handler and subscription mapping, Hue Bridge/button event history, specific app execution logs, sensor trigger/allowed-target settings, previous command-to-report delay distribution. Prioritize target-specific sources ahead of generic system-wide reads. Never imply access to unexposed third-party logs. If unavailable, say exactly what the user/developer should collect.

### 7. Synthesize with calibrated confidence
Answer in this order:
1. **Most likely explanation**, named specifically, with "leading recorded candidate" rather than "caused" where appropriate.
2. **Sequence** of relevant exact events with source-qualified times.
3. **Why it leads**, including alternatives and the strongest contradiction.
4. **Remaining uncertainty**, separated into missing evidence vs incomplete source coverage.
5. **One or two decisive next checks** with their expected discriminator.
Avoid boilerplate, unwarranted certainty, unnecessary speculation and quoting secrets.

## Structured case packet (conceptual; adapt to existing host types)
```yaml
incident: {target_id: null, target_label: null, requested_window: null, transition: null}
topology_edges: []  # {source, target, relation, status, evidence_ids}
timeline: []        # {timestamp, timezone, source, kind, actor, event, evidence_ids}
coverage: []        # {source, scope, retained_window, complete, limit, gaps}
hypotheses: []      # {name, supports, contradicts, assumptions, discriminator, confidence}
next_reads: []      # {source, precise_question, expected_information_gain, cost}
conclusion: {leading_hypothesis: null, confidence: null, unresolved: []}
```
Do not put secrets or raw sensitive configuration in packets.

## Worked calibration: Hue light and SenseCap
Given a recorded SenseCap ON command 13.358 seconds before a Hue ON report, with an intervening OFF report, start with SenseCap as **leading recorded command candidate**, not proven cause. Investigate where SenseCap got the instruction, whether the OFF event is physical or reported state, whether Hue observed a direct controller action, and whether comparable measured delays support an unusual lag. If origin-bearing MQTT/Hue logs are unavailable, explicitly leave causation unresolved.

## Regression benchmark
Run multiple fixture-based cases: (1) Hue activation with preceding OFF and delayed ON, (2) unexpected OFF with independent controller, (3) motion lockout with configured-versus-effective duration mismatch, (4) offline MQTT device versus intentionally powered-off device, (5) Rule Machine app active but target/action path broken, (6) silent/no-history event stream and capped log page.

For each, assert: source identity, transition completeness, correct topology, multiple testable hypotheses, contradictory evidence retained, meaningful decisive next read, no invented tools/data, no secret leakage, non-mutating execution, and deadline fallback. Score investigation quality and evidence correctness separately from narrative style. Do not use word-for-word agreement with another assistant as the success metric.

## Implementation note
This file alone does **not** hook the skill into routing or grant new data access. Integration must reuse the existing investigation intelligence, causal answer planner, evidence receipts, model context budget, validators and host read-only tool dispatch. Prefer a small orchestrator operating on structured evidence over another per-device regex or a second unconstrained agent loop.
