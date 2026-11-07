# RFC: HomeBrainOS Causal Investigator V3 — Evidence-Driven Tool Choice and Verifiable Synthesis

**Status:** Draft for independent Claude/Gemini review — no production behaviour changes  
**Baseline:** HomeBrainOS v0.18.260 (30 October 2026)  
**Owner:** HomeBrainOS maintainers  
**Scope:** Original model-native MCP agent running as an HA add-on; **no new agent and no live Hubitat changes**.

## 1. Why another architectural phase is needed

HomeBrainOS now correctly:
- Resolves named target devices; calls targeted, time-bounded read tools.
- Recovers source-timestamped switch events from its local Historical Journal after live history has rolled over.
- Separates issued `on/off/setLevel` commands, device state reports, app event listeners, archive **source time**, and archive **collector reception**.
- Recovers independently selected input-device histories from the Journal; counts source-time vs reception-only and reports archive gaps/truncation.
- Computes bounded cross-clock *co-occurrence patterns* while explicitly refusing to infer command origin from timing alone.

The 30 October Bathroom Light 1/2 acceptance trace at v0.18.260 found:
- 20 source-timed switch reports, 20 collector-reception switch copies, across two target lights.
- Target app 4013 issued `setLevel(60)` shortly *after* initial ON reports; this cannot identify the preceding ON issuer.
- Native input 7746 motion events notify app 4014 (Shower), **not** an observed target command issuer.
- Archived input 7895 (LWR01 occupancy) returned 5/5 active-reception proximity to ON and 5/5 inactive-reception proximity before OFF. Its original event source clock is unavailable, so exact input-vs-light event order and controller attribution are unverified.
- Archived motion device 7754 returned 160 rows, truncated by journal query; its evidence receipt safely retained 20 rows plus a full-page compact correlation summary.
- The model made 10 rounds / 24 tool calls; total 58.2s; outcome unresolved.

**The core failure is not a missing Bathroom rule.** The tool pipeline fails to turn discovered associations into a disciplined choice of the *next distinct, feasible source* and an appropriately qualified causal conclusion. Multiple source queries can repeat without closing an identified causal edge.

## 2. Code-level finding: final synthesis masks model behaviour

`hubitat-mcp-ai/rootfs/app/unified_incident_synthesis.py::reconcile_ledger_if_needed` currently does:

```python
if gaps and int(facts.get("journal_source_observations") or 0) > 0:
    digest = source_incident_digest(facts)
    if digest:
        return digest, True
```

Whenever archive switch history is recovered in the common missing-native-history case, this **replaces the model-authored answer** with a deterministic digest *regardless of whether the original model explanation was evidence-grounded and useful*. The surrounding `unified_investigation_bridge.reconcile_unified_investigation_answer` and orchestrator publication boundary therefore can mask whether the native agent actually reasoned well.

Keep the digest as an **evidence-preserving emergency fallback**, not the default narrative for all historical investigations. This must not become a naive 'trust the model' reversal: unverified causation, omitted critical events and unsourced absence conclusions remain unacceptable.

Before changing publication:
1. Add privacy-safe, request-scoped instrumentation: `model_draft_claim_status`, `finalization_action` (preserved/corrected/replaced), `finalization_reason`, the count of recovered facts *actually referenced*, and evidence-class coverage. Never log a full conversational prompt or secret-bearing raw MCP result.
2. Introduce **structured claim assertions** with witness IDs, event class, source/clock basis, and limited confidence semantics. Claims about exact timestamps must match source-time witnesses; claims about causing an ON need an actual command issuer/execution witness, not a bridge report.
3. Use a single model-authored final narrative on success. When model claims violate evidence, either regenerate once from a compact verified packet or replace with the current reliable digest. When no violation exists but coverage is partial, retain the narrative and append a short source-gap note rather than silently discarding it.
4. Maintain an explicit consistency-check contract for any final output that includes source-timed events. Tests must cover model overclaim, model under-reporting, correctly qualified causal analysis, and source-recovery gaps.

## 3. Evidence ontology: keep roles and clock provenance separate

Represent compact, immutable investigation facts as:

| Fact edge | Meaning | What it cannot establish by itself |
|---|---|---|
| `SOURCE_STATE_REPORT(device,state,time,source)` | Device/bridge reported a state with a source clock | Who requested that state; electrical physical ACK |
| `HUBITAT_COMMAND(app,device,command,time)` | Hubitat app issued a named command | Upstream reason, receiver success, other controllers' activity |
| `EVENT_NOTIFIED_APP(input,app,time)` | Event dispatched to/subscribed by an app | App executed code or issued a target command |
| `DEPENDENCY_CONFIG(app,input/output)` | Current declared app configuration references entities | Historical execution or settings at event time |
| `COLLECTOR_RECEPTION(input,state,time)` | HomeBrain received an event | Original sensor event timestamp or reliable cross-system event order |
| `HISTORICAL_EXECUTION(app,decision,time,source)` | Independently captured source-typed app execution decision | The command succeeded without matching reported state |
| `EXTERNAL_COMMAND(controller,device,time,source)` | Independently captured upstream action/issuer from that system | Actual state without resulting device report |

Every edge must include: identity proof, source type, clock type, incident time bounds, truncation/retention status, and witness receipt IDs. *Absence of a returned row* must never become a negative historical finding unless coverage guarantees truly support it.

Do not confuse `producedBy` (bridge reporting) with `triggered` (notified listeners), or a current `hub_list_device_dependents` list with event-time execution.

## 4. Dynamic dependency discovery and source feasibility

The **existing unified agent remains the only MCP read selector**. Give it a compact read-only `CausalEvidenceGraph`/dependency-closure *view* (not a second model or hard-coded room-specific route).

Graph starts only from user-verified target IDs and source-verified read results:
- Target -> current Hubitat dependent apps and direct commands.
- Controller app -> explicitly configured input/output entities, when the API exposes usable typed values rather than just a settings-page summary.
- Input -> source-observed app notifications.
- Bridge -> reporting topology. Label transport and integration edges separately from actual command edges.
- Optional connector-specific read capabilities (HA automation traces, Hue bridge behaviour, SmartThings rule history) must be **explicitly discovered, authorized, and available**. Do not imply HomeBrain can read a source it has not connected.

`get_dependency_closure` should be a **bounded projection over already fetched or deliberately model-selected reads**, not a sweeping inventory of ~200 devices/165 automations. Suggested output: up to 30 nodes, 50 edges, 4 levels, provenance and confidence per edge, clear omissions/truncation, plus `nextReadCandidates` with exact supported MCP leaves. Validate limits against HA add-on resource constraints.

Identify the strongest currently open causal edges and ask the model to select one differentiating read:
- Is there an original input source clock?
- Is there a compatible command issuer/execution trace for the same event time?
- Does the upstream system have an available read-only command source?
- Is the recorded app an actual command emitter or only an event subscriber?
- Would the new call only repeat an empty source, a source-time-unavailable collector record or a current config already checked?

A failed or unavailable source is an explicit answerable *capability gap*. Avoid repeated similar reads and language-only word routing.

## 5. Hypothesis and stopping contract

For every investigated causal candidate maintain:

```text
hypothesis
  ├─ observations_for [witness IDs]
  ├─ observations_against [witness IDs]
  ├─ unanswered_discriminator
  ├─ feasible_next_read [tool/args/source, if verified available]
  └─ status: corroborated / contradicted / unresolved / source-inaccessible
```

- **Corroborated** means competing explanations have less support; it is not proof of specific initiator.
- **Verified issuer** requires a matching original command/execution witness, not just a sensor-light pattern.
- Stop when the strongest remaining discriminator has no accessible source or the bounded read budget is exhausted. State the exact missing source and how it could be captured in future.
- Two independent lights responding near-simultaneously are **one coordinated incident** for scoring, not two independent trials.
- Distinguish `command_history` capability checks from individual command rows observed incidentally inside `device_history`.

## 6. Three staged PRs, not another sequence of narrow answer patches

### Stage A — Observability and measurement, no model-output changes
- Record why the deterministic finalizer overrides model draft and how much newly retrieved evidence the model actually used.
- Record unique tool/source categories vs repeats and open discriminators, including real gateway schema errors.
- Add replayable, redacted, frozen investigation fixtures (Bathroom, Bedroom 3 Mesh offline, Livingroom Light 1).
- Acceptance: CI + side-by-side diagnostic of original model draft and published fallback via *metrics only*, without leaking raw prompts.

### Stage B — Typed causal evidence graph and gap-directed reads
- Implement minimal witness-backed edges from existing successful read receipts and declared metadata; do **not** invent upstream capabilities.
- Add a bounded model-visible `nextSourceChoices` result with concrete evidence gain, availability and deduplication rationale.
- Keep free model in the loop selecting actual authorized tool calls. Add cases showing different causal chains and out-of-order/collector-only input timestamps.
- Acceptance: fewer redundant calls; no non-read actions; correct edge-role assignment; no evidence loss when journal API returns only reception records.

### Stage C — Verified claim contract and model-led finalization
- The original model explains its causal hypothesis using typed evidence and a succinct timeline.
- The validator protects against unsupported/excluded claims; deterministic digest is used only when necessary.
- Acceptance: a correct, evidence-grounded model narrative survives; a misleading narrative is corrected; neither can claim missing upstream execution was independently verified; no duplicate timelines.

## 7. Independent review questions

Please review actual implementation, not only this RFC:
1. Is the unconditional journal-digest replacement materially preventing Claude-like natural reasoning?
2. How can final answers be validated by witnesses without falling back into keyword-based sentence checks or always replacing the model?
3. What is the smallest provenance-aware dependency graph that materially improves original model tool choice without context/latency explosion?
4. Which specific Hubitat, HA and Hue upstream read capabilities would be needed to identify the original ON issuer; what remains fundamentally unobservable?
5. How should reception-only pattern correlations be summarized without overstating causal confidence, especially when two lights report the same incident?
6. What acceptance metrics, counterexamples, tests and stop rules should gate the next implementation?
7. What simplifications or removals would reduce overlapping corrections/follow-up gates and repeated tool calls?

Request: identify **incorrect assumptions**, top three architectural changes, minimal ordered migration path, and concrete test fixtures. Prefer a single coherent design over another hard-coded source-specific patch. Propose code diffs only after checking their true dependencies.

## 8. Source files for reviewers

- `hubitat-mcp-ai/rootfs/app/mcp_agent_orchestrator.py` — model loop, tool authorization, journal follow-up, terminal boundary
- `hubitat-mcp-ai/rootfs/app/unified_investigation_bridge.py` — source-verified event collector and causal evidence packet
- `hubitat-mcp-ai/rootfs/app/group_journal_recovery.py` — bounded source and reception journal recovery
- `hubitat-mcp-ai/rootfs/app/unified_incident_synthesis.py` — **unconditional digest replacement**
- `hubitat-mcp-ai/rootfs/app/unified_incident_digest.py` — evidence-grounded terminal formatter
- `hubitat-mcp-ai/rootfs/app/investigation_evidence_cycle.py` — current model read-choice checkpoint
- `hubitat-mcp-ai/rootfs/app/investigation_checkpoint.py` — source gaps and next discrimination prompt
- `hubitat-mcp-ai/rootfs/app/investigation_dependency_leads.py` — current dependency source hints
- `hubitat-mcp-ai/rootfs/app/historical_evidence_journal.py` — local journal semantics, source/collector clocks
- `docs/RFC-INVESTIGATION-V2.md` — previous objectives and safety contract

**Security:** review from source code and a **sanitized** test JSON; remove access tokens, private IP addresses and personal device/network identifiers if sharing outside authorized accounts. No production Hubitat edits in this RFC.
