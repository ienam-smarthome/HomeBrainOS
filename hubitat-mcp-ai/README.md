# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.16.84**.

## Architecture

0.16.84 keeps the accepted 0.16.81-0.16.83 retrieval, adaptive expansion, host timing, and evidence-classification architecture unchanged. The post-synthesis diagnostic guard now preserves the enclosing diagnostic/recommendation mode across numbered bold entity subheadings and preserves the current entity across child fields such as Finding, Evidence, Conclusion, Diagnostic interpretation, Hypothesis, Verification, Action, and Next step unless a different entity is explicitly named. An unscoped entity subheading explicitly clears the previous scoped target, preventing evidence from one outlier leaking into another. Mechanism-specific Verification/Recommendation lines are therefore gated against the correct entity evidence even inside a combined `Diagnostic Hypotheses & Recommendations` section.

The exact 0.16.83 live shape is covered: SenseCap child Evidence can no longer retain an invented `every 5 to 10 minutes` cadence when no host `regular_cadence` exists; LG webOS remains unresolved when not target-scoped and cannot immediately prescribe network/API-specific investigation; Google Nest Hub keeps its already-safe repeated-volume interpretation; and a generic `Cadence:` line is attributed to the source/signal when exactly one host-established regular cadence is available.

0.16.83 keeps the accepted 0.16.81/0.16.82 adaptive retrieval architecture unchanged and removes the remaining Markdown-shape dependency from diagnostic validation. Adaptive diagnostic claims are now checked by entity and claim type, so inline bullet hypotheses receive the same evidence boundaries as numbered diagnostic subheadings. Cadence claims are validated anywhere in the answer, mechanism-specific recommendations require supporting target-scoped evidence, one observed same-second cluster cannot become an `events per second` rate, and threshold-labelled event rows cannot be promoted into proof that a condition or alert action fired.

The 0.16.83 live regression is based on the exact 0.16.82 output shape: SenseCap's unsupported `every 5 to 10 minutes` cadence is replaced with the authoritative scoped row count and host timing limitation; LG's unscoped network/response-time hypothesis and network/driver recommendation are replaced with an unresolved/evidence-gathering conclusion; the Octopus 16-row same-second cluster remains one observed cluster rather than a recurring rate; and the `Low Memory <200MB>` app event is described as event processing/logging rather than a proven threshold trigger.

0.16.82 keeps the accepted 0.16.81 adaptive retrieval architecture unchanged and adds a structural diagnostic evidence gate after synthesis. Each successful adaptive scoped log receipt is classified as `diagnostic_signal`, `repeated_activity`, `sparse_or_neutral`, or `no_observations`. A real timeout/connectivity/very-long-call signal may support a calibrated hypothesis; repeated neutral activity may be reported as an observed pattern but not as a causal mechanism; sparse/no diagnostic evidence must be stated as unresolved. An outlier that was not one of the scoped adaptive targets may not receive a mechanism hypothesis merely because it looks plausible from performance statistics.

The 0.16.82 gate also makes "unresolved" an explicit valid diagnostic conclusion. Model-authored cadence/frequency language from adaptive raw rows is rejected unless host-derived timing establishes a regular cadence, and same-second clustered log activity is not promoted into literal simultaneity. The validator uses this structural evidence classification under the existing evidence-first repair category rather than adding another phrase-specific diagnosis layer.

0.16.81 keeps the accepted 0.16.78-0.16.80 host-planned baseline and one evidence-first synthesis round, but adds a bounded adaptive diagnostic stage after the baseline performance-stat read. Numeric outliers are retrieval triggers only, not health/severity classifications. When warranted, the host selects at most one device and one app and performs one server-side-scoped `hub_get_logs` read for each (`deviceId` or `appId`, `since=6h`, `limit=120`). A quiet case therefore remains three reads; a fully expanded case is capped at five reads, with zero exploratory agent rounds and one final synthesis round.

Scoped diagnostic log evidence is carried into the final synthesis contract separately from the baseline log packet. The final answer may form a calibrated **diagnostic hypothesis** only when multiple current-turn observations support a pattern, and must separate the confirmed finding, diagnostic evidence, hypothesis, missing proof/verification step, and inspection-first action. Timeout/error/very-long-call observations may support a connectivity or stalled-I/O hypothesis, but do not by themselves prove worker-thread blocking, the exact driver defect, or user-visible delay. Exact setting/code changes still require configuration or implementation evidence.

0.16.80 keeps the accepted 0.16.78 host-planned three-read / one-synthesis performance path and the 0.16.79 host-derived timing arithmetic unchanged. Host timing rows now carry an explicit `timingKind` classification: `regular_cadence`, `irregular_intervals`, or `observed_gap`. The final log-observation guard treats that host classification as authoritative: irregular series cannot be presented as cadence, a two-point sample remains one observed gap, and mixed timing sections use a neutral `Observed Timing` heading rather than grouping every median interval under `Observed Cadence`.

0.16.79 keeps the accepted 0.16.78 host-planned three-read / one-synthesis performance path unchanged. The existing log evidence compactor now derives per-source/per-signal timing facts from the full bounded log result: stable cadence requires at least two observed intervals, two timestamps alone remain one observed gap, and same-second multi-source clusters carry their measured millisecond span. The log-observation guard uses those host facts as a precision backstop, so model-authored cadence arithmetic cannot silently turn a 60-second interval into 30 seconds and same-second observations are not promoted into literal simultaneity.

0.16.78 keeps the 0.16.75 evidence-first final synthesis and 0.16.76-0.16.77 normalization/precision contracts, but moves evidence acquisition for broad performance+recommendation requests out of the exploratory model loop. The host now collects `hub_get_metrics`, `hub_get_performance_stats`, and one bounded `hub_get_logs` window directly through the existing `ToolExecutor`; `hub_get_jobs` is added only when the user's objective explicitly asks about scheduler/job/polling cadence. The model still authors the final analysis from those normalized sources.

This host-planned path removes the unrelated full hub-health snapshot, tool discovery, gateway rejection, and pre-finalizer model rounds seen in the 0.16.77 live proof. The normal prompt `Analyse my Hubitat performance and recommend improvements.` therefore targets three Hubitat reads followed by the existing single evidence-first synthesis model round. Requests outside that narrow broad-performance+recommendation class continue through the normal native-function-calling agent.

0.16.78 also persists fixed-vocabulary deterministic repair reasons into the returned response metrics before the request-coordinator child task exits, so the parent API serializer no longer loses them across the asyncio/ContextVar boundary. An evidence-aware log-observation guard restores cited WARN/ERROR text from the current-turn log receipt when causal/generic repair prose would otherwise overwrite the literal observation; already-clean warning lines are left untouched.

0.16.77 keeps the 0.16.75 evidence-first final performance synthesis, the 0.16.76 canonical metric normalization, the 0.16.70 single-provider-pass finalizer, and the 0.16.72 source-budgeted evidence packet unchanged. It adds precision and observability around the remaining live-analysis edge cases rather than another reasoning architecture.

The 0.16.77 evidence contract treats scheduler/job statements as source-bound: when no successful current-turn `hub_get_jobs` receipt exists, final synthesis must not state job counts, alignment, cadence, `sessionTick`/`autoPoll` scheduling, or scheduler conclusions. Raw log windows are also no longer a basis for model-authored exact event/update counts unless a tool or host-produced summary explicitly supplies the filtered count; otherwise HomeBrain reports multiple observations plus the measured time span/cadence.

Performance metric rows separate total model participation into pre-finalizer **Agent model rounds** and the single **Performance synthesis model round** whenever the finalizer timing proves that path. If deterministic validation is required, a privacy-safe fixed-vocabulary **Performance repair reason** row identifies the persisted correction category. No prompt text, device names, credentials, session IDs, or tool arguments are used as metric dimensions.

0.16.76 changed the evidence boundary: explicitly unit-labelled free-memory values are canonicalized to `freeMemoryMB` before final synthesis while preserving the raw upstream value for provenance. HomeBrain never infers a free-memory unit merely from numeric magnitude. The evidence-first contract also requires canonical normalized fields to outrank raw aliases, keeps `stateSize` numeric unless the source defines a threshold, describes returned rankings literally rather than as causal/resource-impact judgments, and reports job/log cadence as observations rather than invented qualitative thresholds.

The key change in 0.16.75 is architectural rather than another phrase-specific patch: final performance synthesis is **evidence-first**. Prose-only assistant drafts from the earlier tool-selection/reasoning phase are excluded from the final performance synthesis context, while native assistant tool-call envelopes are retained so matching tool messages remain valid. The final model therefore reasons directly from the current-turn metrics, performance statistics, jobs, recent logs, evidence ledger, and an explicit performance evidence contract instead of being primed by an unsafe earlier draft.

The performance evidence contract defines what each source class can establish. Metrics support numeric values and explicit alerts/states, not qualitative “healthy/normal/stable” thresholds unless the source itself provides them. Performance statistics support execution time, calls, busy percentage, state size, and returned ordering, not synchronous/blocking/time-out mechanisms or user-visible impact. Job data supports returned scheduling facts, not CPU/load causality or benefits from moving jobs. Recent logs remain observations rather than automatic explanations for longer-window performance totals. When implementation/configuration was not read, recommendations must be inspection-first rather than exact setting/code/schedule changes.

A generic evidence-first validator backs up the model contract for unsupported conditional blocking claims, reporting-to-overhead/log/history causality, qualitative “major/exceptional/very healthy” wording, unsupported ranking/size labels, and categorical “no optimisation needed” conclusions. This is intentionally a backstop; the primary fix is giving the final model normalized evidence and a clean evidence-only synthesis context.

The private performance synthesis packet continues to use source-specific bounded budgets rather than FIFO eviction. `hub_get_metrics`, `hub_get_performance_stats`, `hub_get_jobs`, and `hub_get_logs` each retain a bounded payload slot inside the existing 32k packet, so later job/log payloads cannot silently evict the current metrics source. 0.16.81 carries adaptive scoped log excerpts through the evidence-first contract rather than replacing the baseline `hub_get_logs` packet slot.

When a successful metrics receipt is present, final synthesis is explicitly told to use retained memory/temperature/database fields when available. A deterministic contradiction repair also converts a false metrics-unavailable statement into the actual retained current values; if the detailed payload is genuinely missing, HomeBrain reports a synthesis-context limitation rather than claiming that the hub lacks those metrics.

Z-Wave repair recommendations remain gated on Z-Wave-specific diagnostic evidence such as node, route, topology, mesh, or repair-status detail. A generic `zwHealthy:false` observation can justify inspection, but does not by itself establish that running a Z-Wave repair is required.

The request still reuses normalized, privacy-redacted `ToolExecutor` payloads so measured values remain available without duplicate Hubitat reads and database-size compatibility normalization remains intact. If a non-host-planned performance turn did not obtain recent logs, the finalizer performs one bounded `hub_get_logs` read (`since=30m`, `limit=100`) before synthesis.

The direct production wiring introduced in 0.16.67 remains: `_agent_request()` passes returned outcomes through `performance_api_finalizer.finalize_performance_api_outcome()` before `/api/ask` or `/api/chat` serializes them. 0.16.78 adds the narrow host-planned evidence branch before the normal unified-agent loop only for broad performance requests that also ask for recommendations. Turns without successful performance-stat evidence are returned unchanged.

For complete release history, see [CHANGELOG-INDEX.md](CHANGELOG-INDEX.md).

### Core design

- **Meaning-first control:** semantic plans describe user intent; the model never owns Hubitat device IDs, gateway payloads, or verification.
- **Host-owned grounding:** device identity, capabilities, live reads, writes, and post-write verification are deterministic and evidence-backed.
- **Current-turn evidence:** live/historical factual claims must come from this request's tool evidence, not prior assistant conclusions.
- **Fail-closed synthesis:** deterministic validators localize contradictions or unsupported causal/prescriptive claims without replacing supported analysis.
- **Bounded investigation:** history, logs, scheduler reads, and causal expansion use explicit limits and stronger evidence outranks broad fan-out.
- **Privacy-safe observability:** request metrics use a fixed vocabulary and do not expose prompts, credentials, session IDs, device names, or tool arguments as metric dimensions.

### Performance analysis contract

For broad Hubitat performance/optimisation requests, HomeBrain treats resource/performance statistics as **measured findings** and logs as **recent observations**. A short log window does not automatically explain longer-window performance totals.

A broad performance request that also asks for recommendations uses:

1. Host-planned `hub_get_metrics` for current hub resources and alerts.
2. Host-planned `hub_get_performance_stats` for measured app/device execution statistics.
3. One host-planned bounded recent `hub_get_logs` window (`30m`, maximum `100` rows) before final synthesis.
4. If numeric performance rows cross internal retrieval-policy thresholds, an adaptive diagnostic stage may add at most one device-scoped and one app-scoped `hub_get_logs` read (`since=6h`, `limit=120`). These thresholds choose evidence; they are not health/severity classifications.
5. `hub_get_jobs` only when the user's objective explicitly asks about scheduler/job/polling cadence; without a current-turn job receipt, scheduler-specific conclusions are omitted.
6. The original bounded, normalized, privacy-redacted tool payloads for final synthesis rather than duplicate API snapshot reads; each baseline source class retains its own bounded packet budget, while adaptive scoped excerpts are carried through the evidence contract.
7. One final performance provider synthesis pass; deterministic validators handle localized repairs without another cloud-model round.
8. No exploratory pre-synthesis provider round for the normal broad performance+recommendation path; the host owns only source selection, not answer authorship.
9. An evidence-first synthesis contract explicitly states what metrics, performance stats, jobs, and logs can and cannot establish.
10. Canonical normalized metric fields take precedence over raw provenance aliases; explicitly unit-labelled free memory is normalized to MB without guessing unlabeled units.
11. Configuration/implementation evidence is required before prescribing exact polling, reporting, retry, timeout, blocking-model, staggering, shifting, moving, scheduler intervals, job offsets, or reductions in observed call/report volume.
12. Raw log rows support observations; host-derived timing summaries carry authoritative timing kinds: regular cadence, irregular repeated intervals, or a single observed gap. Only `regular_cadence` may be presented as recurring cadence; `irregular_intervals` must remain median/range observations, and `observed_gap` must not be promoted into recurrence.
13. Adaptive scoped evidence is structurally classified before a diagnostic conclusion is accepted. `diagnostic_signal` may support a labeled calibrated hypothesis; `repeated_activity` supports only an observed-pattern interpretation unless stronger evidence exists; `sparse_or_neutral` and `no_observations` require an explicit unresolved conclusion. An outlier without a scoped adaptive receipt is also unresolved rather than assigned a plausible mechanism. These boundaries apply regardless of whether the model uses numbered headings, inline bullets, prose paragraphs, or another Markdown shape. Numbered entity subheadings preserve the enclosing diagnostic/recommendation mode, and child fields inherit the current entity unless another entity is explicitly named.
14. Exact event/update counts require an explicit tool/host filtered count rather than manual model counting. A one-second cluster is not a recurring events-per-second rate.
15. Literal WARN/ERROR observations cited in the answer are preserved from current-turn log evidence; causal boundaries are appended separately rather than replacing the observed message.
16. Z-Wave-specific diagnostic evidence is required before recommending a Z-Wave repair.
17. A successful `hub_get_metrics` receipt must not be contradicted by a final claim that memory, temperature, or database metrics were unavailable when the retained payload contains those fields.
18. A threshold label in an app name plus an `Event:` payload proves event processing/logging, not that the threshold condition evaluated true or an alert action fired.
19. A generic cadence statement should identify its source/signal when the host evidence contains exactly one established regular cadence.

The final answer must keep these distinctions explicit:

- High execution time or call volume is measured; an implementation mechanism is not established unless directly supported by current-turn implementation/configuration evidence.
- Returned ordering/percentages may be described literally (for example highest returned `pctTotal`), but should not be promoted into “primary consumer”, “highest impact”, “highest resource usage”, or other causal/resource judgments that the source does not define.
- Numeric `stateSize` is a measured value; “large” requires a source-provided threshold or classification.
- Adaptive diagnostic evidence may justify a labeled, calibrated hypothesis only when the scoped evidence contains an actual diagnostic signal. Repeated neutral activity is an observation, not proof that it caused the busy percentage. Sparse neutral logs are positive evidence that the targeted read did not reveal the mechanism, and the answer should say so.
- A scheduled-job list proves returned jobs/cadence/alignment, not CPU spikes, CPU load, UI stuttering, delayed automations, hub overhead, or that changing offsets will improve performance. Without a successful current-turn scheduler/job source, do not state scheduler-specific facts.
- Database size is reported numerically in MB; qualitative labels such as normal/healthy/small/large require a defined current-turn threshold.
- Frequent device reporting proves activity, not material hub/background overhead, log growth, history slowdown, or a performance cause by itself.
- Repeated app triggers are observations; they do not by themselves establish an efficiency problem.
- A high app busy percentage is measured; it does not by itself establish inefficient loops, excessive trigger frequency, or another implementation mechanism.
- Empty/no-active health alerts support “no active alert”, not categorical “very healthy” or “no optimisation needed” conclusions.
- Recent connectivity/error logs are observations; they may support a labeled hypothesis when aligned with the measured outlier, but they do not by themselves prove overall hub instability or the exact mechanism behind longer-window performance statistics.
- Same-second clusters prove bounded timestamp clustering, not literal simultaneity or a recurring per-second rate.
- A threshold-labelled event proves the event was observed/processed, not that the threshold condition fired.
- `zwHealthy:false` is a warning/health observation, not sufficient evidence by itself to prescribe a Z-Wave repair.
- `NETWORK_BACKUP_FAILED` proves an active alert, not imminent data loss or the status of other backup methods.

## Setup

1. Install and configure **MCP Rule Server** on Hubitat.
2. Copy its local MCP endpoint and token.
3. Create an API key in your ollama.com account.
4. Configure the add-on in Home Assistant.
5. Start the add-on and open its Home Assistant sidebar panel.

Typical configuration:

```yaml
hubitat_mcp_url: http://192.168.1.100/apps/api/123/mcp
hubitat_mcp_token: YOUR_HUBITAT_TOKEN
ollama_direct_cloud_enabled: true
ollama_direct_cloud_base_url: "https://ollama.com"
ollama_direct_cloud_api_key: YOUR_OLLAMA_API_KEY
ollama_direct_cloud_model: gemma4:31b-cloud
require_sensitive_confirmation: true
morning_health_check_enabled: true
morning_health_check_time: "07:00"
pushover_enabled: false
pushover_app_token: ""
pushover_user_key: ""
pushover_device: ""
ha_tts_enabled: true
ha_tts_notify_service: ""
ha_tts_media_stream: ""
```

The add-on uses authenticated Home Assistant ingress. The direct host-port mapping is disabled by default. Do not expose the direct port unless another authenticated access-control layer protects it.

## Optional local Ollama fallback

If you run `ollama serve` on a machine on your LAN, HomeBrain can try that model first and fall back to Ollama Online when it is unavailable:

```yaml
ollama_local_enabled: true
ollama_local_base_url: http://192.168.1.50:11434
ollama_local_model: gemma3:12b
ollama_local_connect_timeout_seconds: 3
ollama_local_timeout_seconds: 12
ollama_local_keep_alive_seconds: 120
```

`ollama_local_connect_timeout_seconds` bounds reachability failure, while `ollama_local_timeout_seconds` allows more time after a connection for cold model loading. `ollama_local_keep_alive_seconds` controls how long the local Ollama model remains resident after inactivity.

## System Check and Pushover

`HealthAuditService` performs read-only Hub/MCP/device/battery/automation/log health checks and stores the latest snapshot under `/data`. The dashboard exposes the latest result, new/resolved findings, a manual **Run system check now** action, and **Send report to Pushover** when Pushover is configured.

Useful options include:

```yaml
health_check_log_hours: 24
health_check_low_battery: 20
health_check_stale_hours: 24
health_check_long_stale_hours: 168
health_check_cluster_minutes: 15
health_check_motion_active_hours: 2
```

Scheduled health checks are read-only. Pushover delivery failure does not discard a completed audit.

## Home Assistant TTS

HomeBrain can use the Home Assistant mobile-app notify/TTS path when browser speech is unavailable. Leave `ha_tts_notify_service` empty when there is only one `notify.mobile_app_*` target; otherwise configure the desired service explicitly. `ha_tts_media_stream` may be left empty for the normal stream or set to a supported alarm stream when required.

## Safety and evidence boundaries

Sensitive writes use the structured confirmation policy. Confirmed actions are revalidated before execution and mutation success is reported only from verified tool evidence.

For history and causal questions, HomeBrain separates:

- observed state/event history,
- direct command or execution provenance,
- configuration/topology evidence,
- temporal correlation,
- hypotheses and unresolved gaps.

Configuration alone does not prove a specific automation caused a transition. Temporal correlation alone does not prove who or what initiated an event. Unverified device-event streams are presented as recorded-event estimates rather than exact physical history.

Precise-location attributes are stripped from provider-bound tool results. Current-turn evidence is isolated per request and prior chat conclusions are not treated as live proof.

## API

These endpoints are intended to be reached through Home Assistant ingress:

- `GET /api/status` — MCP/Ollama/runtime readiness.
- `GET /api/dashboard` — cached live-state dashboard counts.
- `GET /api/health-audit` — latest stored System Check and schedule state.
- `POST /api/health-audit/run` — run the read-only System Check immediately.
- `POST /api/ask` — process a request through the unified MCP agent.
- `POST /api/chat` — compatibility alias for `/api/ask`.
- `POST /api/refresh` — refresh MCP tools and device manifest.
- `GET /health` — add-on health probe.

`/api/ask` returns the stable unified-agent envelope, including the answer, request class, evidence receipts, privacy-safe metrics, model participation, elapsed time, and packaged add-on version.

## Development and validation

The blocking test/release gates include Python compilation, architecture-module-map drift detection, the full pytest release gate, repository/version alignment, import analysis, release-assurance contracts, and a container smoke build.

Runtime modules under `hubitat-mcp-ai/rootfs/app/` must be documented in `docs/RUNTIME-MODULE-MAP.md`. Any runtime change requires a new add-on version and matching release notes.

For release-by-release technical history, use [CHANGELOG-INDEX.md](CHANGELOG-INDEX.md).