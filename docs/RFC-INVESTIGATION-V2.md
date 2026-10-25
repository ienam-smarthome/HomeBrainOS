# RFC: Investigation V2 — evidence-first agent replacement

Status: Proposed architecture, design only (no runtime behaviour changed).
Basis: HomeBrainOS main at version 0.18.121 (25 October 2026), and read-only live investigation traces 0.18.118–0.18.121.

## Decision

Replace the current accumulation of intent-specific orchestration, causal policy modules, answer text rewriting and post-hoc "fail closed" summaries with a **single request-scoped evidence case file** and a general **plan → acquire → interpret → verify → answer** loop. Execute the migration bottom-up as a strangler replacement; preserve existing HomeBrain control permissions and explicit confirmation handling. This RFC is not a claim that the new runtime is implemented.

Keep the LLM responsible for selecting useful questions, choosing supported read tools, comparing alternatives, and writing clear answers. Keep deterministic host code responsible for tool permission gates, actual tool schemas, source/identity/time provenance, retrieval coverage, cross-source evidence association, and validation of *claims*, not rewriting narrative wholesale.

**Non-goal:** hardcode Livingroom Light 1, FP400, individual user phrases, named apps, or fixed sensor conclusions. Lighting is an acceptance fixture, not production routing logic.

## Measured codebase and structural diagnosis

At this revision, hubitat-mcp-ai/rootfs/app contains **218 Python files (~3.55 MB)** and tests contains **442 entries (~3.22 MB)**. Specific critical paths:

- mcp_agent_orchestrator.py: ~6,419 lines / 311 KB. Tool execution, multiple causal specialist paths, source prefetch, decision gating and terminal synthesis are interleaved.
- final_answer_coordinator.py: ~980 lines / 48 KB. Rebuilds many separate evidence packets, creates numerous synthetic user-role instruction messages, invokes multiple validators, and may fall back to a narrow direct answer.
- device_history_service.py: ~1,189 lines / 46 KB. Resolves entities, fetches source events, handles timezone and temporal analysis, separately reads command events, and emits specialized receipts.
- history_temporal_analysis.py: ~1,892 lines / 70 KB. Computes state intervals, but also contains extensive answer/Markdown text correction logic.
- synthesis_validator.py: 379 lines, chains multiple regex and specialized causal/performance guards.
- shared_investigation_completion.py: ~794 lines / 40 KB; applies additional domain and historical guards **after** the model synthesises, so a final answer may omit useful evidence. Its generic causal path deliberately sets partial=True and rootCauseVerified=False independent of actual source-class reads; "unresolved" is therefore not a discriminating quality metric.
- historical_window_integrity.py: ~219 lines: an explicit two-dated-time request parser inspects retained **switch** event rows, but its final calibration may entirely replace an answer even if **command** evidence was separately retrieved for the same window.
- history_time_windows.py: another independent time/window resolver with different input representation; reconciliation between the two is not guaranteed.

This is architectural overlap, not proof that every module is wrong. Safety guards are valuable but need one authority, one proof model, and non-destructive output checks.

## Failing live acceptance case: 24–25 October 2026

The 0.18.121 read-only response to an overnight living-room incident said "No bounded on interval was established" and failed to use the evidence to explain possible mechanics. The collected **windowEvents** contain:

- 24 Oct 18:37:59.578 +01:00: command-on from button app 1251.
- 24 Oct 23:00:07.493 +01:00: command-setLevel(60) from app 4019, with a reported level=60 at 23:00:08.586.
- 25 Oct 00:30:06.185 +01:00: command-setLevel(30) from app 4019, with level=30 reported at 00:31:52.484.
- 25 Oct 00:41:40.085 +01:00: command-off from test rule 4246.
- 25 Oct 00:49:52.008 +01:00: command-setLevel(30) from app 4019.
- 25 Oct 01:09:41.597 +01:00: command-off from button app 1251.

The command record at 00:41 proves only that an OFF was *issued*; it does not establish physical execution. Level 30 reported after 00:30 and setLevel at 00:49 are distinct kinds of evidence. The incident crossed a UK DST transition and source event timestamps retain their own +01:00/+00:00 offsets. The retained switch history alone does not establish uninterrupted physical ON between these clocks.

The runtime also reported sourceCompleteToWindowStart=True and sourceIntegrityVerified=False: **page reach** must never be silently upgraded to source completeness. It reported 49 generic device events, but only 11 switch rows available for state-interval analysis. An explicit latest-N history slice cannot be treated as a complete event stream. The current historical-window guard reads observed switch rows only, ignores positive command clues, and replaces a useful conditional explanation with a generic gap warning.

An earlier 0.18.120 run inferred "no ON recorded -> controller unaware -> hub reboot caused failure", which was not evidenced. The v0.18.121 guard stopped that false positive but created an evidence-omission false negative. Both failures are captured by the same acceptance case.

## New contracts (one source of truth)

### 1. Request envelope

An LLM-interpreted goal with host-validated fields:
- original_user_request, target_entities with canonical Hubitat IDs, time range as timezone-aware absolute instants (or unknown/ambiguous), read-only/write intent, core questions, and requested output specificity.
- Semantic task intent must **not** be selected through exact-word routing. A host permission check may refuse a write independently of model planning.
- Preserve one request objective across tool selection, case-file construction and answer validation.

### 2. Normalized evidence item

Every record in a unified case file must carry:
- record_id, source_request_id, tool/operation, source category, target_id and producer_id **when established**, timestamp instant + original offset, observation kind, normalized action/state/quantity, raw reference/brief display payload.
- Epistemic stage: `command_issued`, `state_reported`, `app_log_statement`, `config_stored`, `app_execution_observed`, `transport_ack`, `independent_physical_observation`. Never promote one stage to another by similarity or timing alone.
- Retrieval envelope: query target, filters, requested and actual coverage, returned rows, source retention/page reach, pagination cursor, oldest/newest, truncation, source integrity and error information. `page_reaches_start` and `source_complete` are **separate dimensions**.
- Observations must be deduplicated by stable content/source/time identity and presented in true absolute chronological order, not raw text order. Do not throw away commands when state evidence is absent.
- Distinguish `triggered[]` listeners from `producedBy` command issuers, with neither automatically proving the upstream actor.
- Preserve the event-time configuration versus current stored settings distinction.

### 3. One case-file builder

Build one data model from all authorized MCP receipts:
- entity index and ownership/dependency candidates;
- one absolute-time event and command ledger;
- observations, claim candidates, directly contradicted observations, unresolved source windows;
- material incident transitions/boundaries and their independent source links;
- independently verifiable hypotheses with positive evidence, conflicting evidence and missing discriminator;
- sources queried and what they actually returned.

All consumers (planner, model, validator, API, UI) read this same normalized case file. Domain adapters can interpret temperature, light/occupancy, device health, MQTT or Rule Machine events but cannot invent events, source completeness or causal assertions.

### 4. Adaptive investigation loop

For each step, the model selects a **missing discriminating question**, not an app-specific hard-coded path. The host maps that question to available MCP tool schemas and approves only real read operations. After reading a source, update the case file; stop repeating queries whose result cannot improve coverage (e.g. same native 11 retained events with successively larger hoursBack). Identify whether next reads can distinguish hypotheses; fetch only while the expected information value justifies cost and available budget. If no records exist, produce the best supported partial answer **with the actual command chronology**.

Read-only observation never authorizes an automation change. Confirmation and write reconciliation stay behind the existing independent write security boundary.

### 5. Evidence-first synthesis

Model receives a concise, ordered, citable case file with the original user question and these response obligations:
1. direct best-supported answer first;
2. material confirmed observations and exact times/producers;
3. ranked plausible explanations, including contradictory evidence;
4. decisive missing observations and one practical next step;
5. calibrated language: *observed*, *consistent with*, *plausible*, *unverified*.

A command issued at 00:41 is preserved whether or not a physical OFF is verified. The validator checks atomic claims against typed records and asks for targeted revision, **never** replaces the entire narrative with one broad stock answer. A safe partial answer still states observed commands and their limitations.

### 6. Evidence-grounded quality assessment

Record separately:
- target resolved, requested history-window coverage, commands checked, physical state reported, config read, logs checked, hypothesis discriminators evaluated;
- incorrect or unsupported factual claims;
- useful source-backed facts omitted from the answer;
- expected runtime/AI cost and tool reads;
- usefulness/readability assessment from golden-case checks.

`success: true` means execution, not proof. `outcome: unresolved` can coexist with a useful well-supported partial diagnosis; do not treat it as a model-reasoning score.

## Implementation stages and rollback

**Phase A — Test-first baseline (no production switch):** anonymized fixture replay using actual 0.18.119–0.18.121 receipts (remove private IP/device secrets); golden assertions require retaining command chronology, correct BST/GMT time, explicit unknown state boundaries, and avoiding unsupported reboot/sensor attribution. Add adversarial fixtures for zero rows, page-truncated data, mismatched targets, and fabricated command producers. Require positive/negative tests: no hallucination **and** no erasure of relevant evidence.

**Phase B — Canonical read contract:** new `investigation_v2` package with typed receipt/event/coverage records and universal source adapters, proven with unit/property-based tests. Keep old runtime intact. Reject contradictory source schemas early and preserve raw receipt references for audit.

**Phase C — Planner and evidence acquisition:** one bounded model-driven planner + verified MCP tool manifest, dedupe and information-gain budget; no device-name or investigative-keyword routing. Keep write side isolated.

**Phase D — Case-file grounded synthesis:** a single structured claim/evidence checker; model authors the explanation, a structural verifier returns exact unsupported or omitted claim IDs for correction. Replace full-answer guards as each equivalence suite passes; retire old modules rather than adding more layers.

**Phase E — Shadow comparison:** run V2 read-only against stored fixtures and optionally side-by-side with V1 behind a setting. Log deltas and timings without duplicating physical/control writes. Blind-rank answers on completeness, causality calibration, clarity, and latency. Never force V2 on all users while failing gates.

**Phase F — Cutover and deletion:** switch the read-only investigation path when all golden cases pass; remove superseded causal prompt policy/guards, specialized completion chains and duplicate window parsing. Maintain the existing deterministic quick status path and write confirmation path. Roll back by feature flag on failure.

## Release gates (must all pass)

1. **Historical evidence preservation:** no observed in-window command with relevant target/provenance silently omitted from an incident answer; no claims of physical execution based on command-only records.
2. **Causal calibration:** no report that hub stress "caused" a light failure from temporal coincidence. A registered handler delay is a distinct observation, not proof of a specific missed timer.
3. **Temporal correctness:** handle offset-bearing timestamps across UK DST fallback, including repeated local-hour ambiguity without assigning a guessed fold.
4. **Coverage provenance:** a paginated endpoint success or page reaching a boundary does not certify a complete state event stream; requested `hoursBack` never becomes proof of actual history coverage.
5. **Generalization:** solve unrelated device incidents (MQTT watchdog, hot-water temperature, internet allowance, rule configuration) with the same case-file and no question-specific production code.
6. **Efficiency:** redundant query elimination, bounded planning/repair rounds and fewer model-facing duplicate evidence packets. Track 50th and 95th percentile latency compared with V1.
7. **Safety:** no write without the established confirmation boundary; no credential leakage or fresh unsupported device identity; robust handling of malformed/untrusted MCP payloads.
8. **Maintenance:** old specialized logic is *removed*, not stacked indefinitely. A shrinking V1 read-path line count is a migration metric.

## Answer expected for the current fixture (grounded but provisional)

"The 18:37 button app issued an ON command, while App 4019 later issued brightness commands. The Night Idle test issued OFF at 00:41, but the supplied state history does not establish that this OFF took effect. App 4019 sent another setLevel command at 00:49, and the button app sent an OFF command at 01:09. This makes a simple 'no OFF was attempted' or 'hub reboot caused it' explanation untenable. A keep-on sensor veto, missed input, and ineffective or subsequently reversed OFF remain plausible; the retained sensor and switch history cannot distinguish them. Verify event-time sensor states plus an independently reported switch state around 00:41–00:49, or capture the next incident before changing the light."

This is an illustration of answer quality, **not** a confirmed retrospective root cause.

## Architectural boundaries

The host controls tool permissions, source identity and time integrity. The model proposes information needs, reads only advertised tools, compares source-backed hypotheses and writes prose. The case file tracks claims and unknowns. Structural validation vetoes unsupported **claims**, not relevant incident records. Presentation stays concise. This separation is intended to make HomeBrain capable of reasoning like a competent investigator without copying another provider's proprietary model internals.

## Rejected alternatives

- Add another named lighting/sensor route: reproduces narrow historical repairs and cannot generalize.
- Increase model rounds only: 0.18.121 used six cloud model rounds and still discarded critical commands.
- Remove all evidence guards: invites the false 0.18.120 "missing ON event caused failure" verdict.
- Rewrite the entire runtime in one merge: high regression risk to controls, app transport, and existing safety gates. Use staged equivalence and shadow tests.
