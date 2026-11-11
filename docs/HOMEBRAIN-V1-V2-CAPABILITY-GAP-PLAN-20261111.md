# HomeBrainOS V1 vs V2 — source-verified capability gap and next-stage plan

**Date:** 11 November 2026  
**Source baseline:** Repository `main` immediately after V2 alpha.48 (pre-alpha.49 change); V1 add-on config `0.18.459` (stable); V2 add-on config `2.0.0-alpha.48` (experimental). The alpha.49 candidate changes only V2's optional read-only monitor-history tool and its supporting tests/docs. **GitHub source versions do not establish installed runtime versions.**

**Scope and evidence strength:** This is a *repository feature comparison* plus limited **private user-supplied first-answer reviews**, not an independently run V1-vs-V2 benchmark. Available V2 live samples are non-random, previously exposed histories (PC, Fridge/Freezer, sensors, TV/Mini PC), and cannot establish overall accuracy, safety or latency uplift. Avoid putting private IDs, household data, OAuth URLs, tokens or Technical JSON in public docs.

## Executive assessment

- **V1 is broader, established and operationally integrated.** It has many specialist modules and protections. The v1 app contains multi-provider/local/cloud/fallback routing, optional historical journal, automation/health services and mature read/write confirmation paths. Those are code-present options, **not proof that every feature is enabled or working in an installed system.**
- **V2 is deliberately smaller and model-led.** It uses the connected MCP catalog directly with read/write confirmation gates; supports an independent external hub-diagnostics recorder, bounded in-memory follow-up source recall, evidence-sidecar metadata, voice/TTS UI and optional separately authenticated **Hub & Device Monitor** saved-device-history queries. It does **not** reuse V1's host-owned causal planner, automatic synthetic answer rewrite, historical journal, scheduled health audit or provider failover orchestration.
- **V2 has established one real advantage:** on user-supplied alpha.47/48 captures, a model-selected local monitor-history tool returned historical power, temperature and humidity even when native Hubitat event history lacked power rows. The v1 journal's targeted event allowlist is not a general numerical wattage historian; the separate Hub & Device Monitor provides that archive.
- **Do not automatically port V1 in bulk.** Transfer only source-verifiable primitives, read/write safety contracts and evidence retrieval capabilities whose absence repeatedly harms held-out V2 acceptance. Preserve model reasoning freedom, privacy and an unchanged stable V1 deployment.

## Repository capability comparison

| Domain | V1 repository code (0.18.459) | V2 repository code (alpha.48 → 49 candidate) | Current conclusion |
|---|---|---|---|
| Product status | Stable, boot auto, independent add-on | Experimental, boot manual, independent add-on | Maintain V1 as default; no cutover yet |
| AI and tool architecture | Layered unified MCP agent, semantic/device/read services, causal investigation planners, host evidence guards, many domain modules | Smaller direct model-native MCP loop, live gateway-leaf schema discovery, model-owned extra evidence sufficiency review, source-side metadata | V2's simpler model-led approach is the primary design asset |
| Provider routing | Ollama Cloud, local model settings, optional paid/Anthropic, account/failover options | One configurable Ollama-compatible endpoint/name/API key per deployment; no v1 multi-provider failover engine | V1 broader; V2 fallback is a later optional milestone |
| Hub device reads and writes | Device control service, rule analysis/authoring pathways, sensitive confirmation and native permissions | Native MCP read and model-selected operations with confirmation protection, without v1 authoring orchestrator | Do not assume V2 has feature parity or enable writes for read-only acceptance |
| Rule Machine/automation investigation | Rule Machine-specific discovery, rule diagnostics, decision / source services | Native MCP tool catalog and generic read-only evidence; no matching v1 host-owned authoring workflow | Validate parent identity, dated trigger schema and mutations separately before parity |
| Event/history/causal reasoning | Optional historical websocket journal, device-history services, command/source roles, causal shadow and publication guards | Native event scopes, per-attribute clock metadata, original tool receipts, source completeness, model-led review | Compare the two on held-out first answers, not count of code paths |
| Historical numeric sensors | Native events plus specialist read logic; v1 journal's selected websocket attributes are not a full wattage store | Optional monitor API with saved power/temperature/humidity/setpoint/level; source-derived interval extrema, report/held/missing, no duplicate polling | V2 monitor bridge is a working direction; extend general evidence fidelity, not storage yet |
| Multi-device comparisons | Multiple host services and read policies, no demonstrated live apples-to-apples result | Alpha.49 candidate: one model-selected compare call, shared UTC window, per-device extrema/gap runs | Test first answer, latency, returned window and source gaps |
| Hub diagnostics | External resource recorder, long-running graph/incident workflows | Independent external recorder with resource plots and reboot timeline | Audit functional parity using same incident timeline and data coverage |
| Proactive features | Optional morning health-check scheduler, audits, automation ideas, Pushover options | No equivalent scheduled whole-house audit; external diagnostic probe is separate | Defer until model's read-only evidence quality is reliable |
| Voice/UI | Browser/HA voice and TTS, broader UX and model controls | Simple Ask/Chat, Speak and optional HA TTS, Hub Diagnostics, test/benchmark panels | Compare actual voice execution reliability separately |
| Conversation context | V1 conversation-context and several incident/history mechanisms | V2 bounded in-memory source index/excerpts and tool-driven prior evidence recall; no persistent long-term incident store | Preserve source boundaries; longer-term memory should be opt-in |
| Evaluation | Large accumulated tests, experiments and historical regression contracts | Synthetic offline lab, source-ledger/AB tools, current live first-answer packet workflow | Freeze held-out packets; compare actual claims + cost, not CI counts |

**Code anchors (relative paths):** `hubitat-mcp-ai/config.yaml`, `hubitat-mcp-ai/rootfs/app/app.py`, `hubitat-mcp-ai/rootfs/app/historical_evidence_journal.py`, `hubitat-mcp-ai/rootfs/app/homebrain_agent.py`, `hubitat-mcp-ai-v2/config.yaml`, `hubitat-mcp-ai-v2/rootfs/app/agent.py`, `hubitat-mcp-ai-v2/rootfs/app/device_monitor.py`, `hubitat-mcp-ai-v2/rootfs/app/external_hub_diagnostics.py`, `hubitat-mcp-ai-v2/rootfs/app/conversation.py`, `hubitat-mcp-ai-v2/rootfs/app/reasoning_experiment.py`.

## Sequenced development/acceptance gates

### Gate A — finish historical comparison correctness (alpha.49 candidate)

- Offer one OPTIONAL **read-only** `homebrain_read_device_monitor(mode=compare)` request for 2–5 device IDs with **one shared UTC interval**, using the existing monitor API's exact per-device custom reads.
- For relative 1h/6h/12h/24h comparison, pin the end to the last completed UTC five-minute boundary; show this adjustment, do not pretend the window ends at the current second. Exact custom user windows retain supplied boundaries.
- Return concise per-device *source-calculated* extrema (all saved vs report-containing power), report/held counts, missing and explicit-null counts, plus consecutive gap/held runs and longest gaps. Label **bin coverage only**, not device availability, physical load continuity or proved cause. Full bin lists remain available via individual history mode.
- No retry, duplicate recorder, new sampling/polling, model answer rewrite or permissions change. Verify via fictional regression and CI; then require a real installed, unseen, read-only multi-device question before calling it successful.

### Gate B — benchmark V1 and V2 on the *same source problems*

Run the same held-out questions, closely timed and read-only, against verified installed V1 and V2 builds; preserve independent first answers. Sample matrix:
1. **Current state:** Two exact devices with distinct current values/status, plus stale telemetry.
2. **Historical measurement:** One device with saved power bins containing a report, held bin and absent period. Match unit/window/extrema and report freshness.
3. **Comparative measurement:** Two devices with different maxima and missing runs; both systems must state what historical stores were actually checked.
4. **Historical humidity:** Time-window threshold crossing with sparse samples; distinguish earliest observed crossing from actual unobserved crossing time.
5. **Causal latest OFF:** Correct state reporter versus command issuer versus downstream triggered listener; record which discriminating native logs/rule paths were verified.
6. **Hub resource incident:** Distinguish actual hub critical-memory reboot marker, platform update and unknown memory consumer.
7. **Rule Machine read-only review:** Parent native identity, dated-trigger availability, configured rule versus proven execution, no mutation.
8. **Operational safety:** Ordinary read must never control devices; separately test confirmation UX on synthetic/dev/test targets before enabling live writes.

For each system, record **factual grounding**, **source completeness**, **causal calibration** (N/A when inapplicable), **usefulness** (0/1/2), confirmed errors, model rounds, completed tool reads, elapsed time, unknowns and confidence-language mistakes. Use original successful receipts and explicit event/window timestamps; one failed read does not prove a source empty. Preserve private packets outside public GitHub. Compare absolute supported claims and false definite claims, not whether one model uses more tools or has more host modules.

**Exit gate proposal:** Across at least twelve *new* source-real read-only first answers spanning six domains, no unapproved actions, zero definitive causes unsupported by receipts, and a strong majority of questions with correct target/metric/window and no hidden missing source. Evaluate against same-window V1 baseline and inspect all failures; do not treat synthetic CI or already-exposed incidents as this gate.

### Gate C — choose which V1 capabilities to reintroduce

Only after Gate B:
1. Prioritise **general** native history pagination/archival coverage and source-schema affordances, if source-real failures persist after alpha.49. Prefer the existing monitor + native MCP over duplicate storage.
2. Recover **Rule Machine identity/authoring contracts** as typed read-only MCP guidance first. One-time dated native authoring remains blocked until its parent and dated trigger contract are independently verified.
3. Evaluate **provider resilience** (local/cloud fallback, explicit spending/quotas, provider error clarity) separately. Never silently change or escalate to a paid route.
4. Validate **confirmed device commands** with explicit user authorization, preflight and post-action observation. No generic read-only question should obtain write rights.
5. Only then decide whether V1's scheduled audits, automation ideas, persistent journal, notifications and voice stack provide measured user value beyond existing Hubitat/HA workflows.

### Gate D — decide V2 cutover deliberately

Keep V1 stable until V2 has comparable read-only usefulness and safe, user-approved actions in held-out source-real tests. Compare performance/cost under the **same model/provider configuration** where possible; otherwise disclose non-equivalent conditions. Do not infer any installed feature from packaged repo defaults. Preserve rollback instructions, no cross-version data migration without explicit request, and retain the independent Hub & Device Monitor archive.

## Current unknowns

- Whether installed V1 version matches repository v0.18.459, and which optional V1 journal/health/provider features are enabled.
- Whether native Rule Machine one-time authoring parent identity and dated-trigger schema are now resolved upstream.
- Whether V2 multi-device comparison actually reduces errors or model latency in unseen source-real tests.
- Whether the monitor export's timestamp/provenance semantics generalise across all optional sensor/level metrics.
- Whether new actual failures justify a separate historian. **Not justified by the current successful monitor-API examples.**
