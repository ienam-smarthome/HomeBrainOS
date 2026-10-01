# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.16.86**.

## Architecture

0.16.86 keeps the accepted performance retrieval/model architecture unchanged and closes the remaining evidence-use defects exposed by the 0.16.85 live proof. A quiet broad-performance request remains three reads / zero exploratory agent model rounds / one synthesis round; a strong-outlier request remains capped at five reads / zero agent rounds / one synthesis round.

Adaptive target identity is now carried from the exact `hub_get_performance_stats` row into the scoped diagnostic evidence receipt. The receipt records the selected target kind, ID, name and the triggering performance-row values (`pctBusy`, `pctTotal`, `averageMs`, count/state/runtime fields when present). This is authoritative provenance even when the scoped log read returns zero rows. HomeBrain therefore never needs to re-resolve or guess which app/device won adaptive selection. In particular, a different app ID from the app shown as highest `pctBusy` is not automatically an error: a row may legitimately win because it crosses the independent average-execution or total-share retrieval threshold.

Hubitat WARN rows with comma-formatted method durations such as `method runQ ... ran for 166,621ms` are now classified as `diagnostic_signal`. Repeated very-long operation durations may support a calibrated stalled/excessively-long-running-operation hypothesis. They do not, by themselves, prove a network cause, worker-thread blocking, the exact driver defect, or user-visible delay. Timeout/HTTP/reachability signals remain a separate connectivity/failure hypothesis class.

Literal WARN/ERROR evidence is now matched by structured source identity (`kind`, ID and name), not only the raw `app|id|name` token. A final literal-observation pass runs after generic performance semantic repair so a concrete warning such as MCP Rule Server `slow internal GET` cannot be reduced to generic "returned activity" wording.

Same-second cluster evidence remains inspection-first. A measured cluster may justify reviewing whether grouped reporting is expected/configurable, but without configuration evidence HomeBrain does not prescribe staggering, offsetting or changing report frequency as necessary or performance-improving.

0.16.85 keeps the accepted performance retrieval architecture unchanged and consolidates the last presentation-integrity boundary. The broad performance path remains host-planned: a quiet case uses metrics, performance stats and one bounded recent-log read; a strong-outlier case may add at most one device-scoped and one app-scoped six-hour diagnostic log read. The normal path still uses zero exploratory agent model rounds and one final synthesis round.

The diagnostic validator recognizes child fields by semantic role instead of exact model labels. `Finding`, `Confirmed Finding`, `Diagnostic Finding`, `Evidence`, `Diagnostic Evidence`, `Observed Evidence`, `Conclusion`, `Hypothesis`, `Diagnostic Hypothesis`, `Verification`, `Action` and `Next step` preserve the current diagnostic target unless another entity is explicitly named. Host timing is rendered atomically from one timing record, so a source/signal name is never attached to another signal's interval statistics.

For complete release history, see [CHANGELOG-INDEX.md](CHANGELOG-INDEX.md).

### Core design

- **Meaning-first control:** semantic plans describe user intent; the model never owns Hubitat device IDs, gateway payloads, or verification.
- **Host-owned grounding:** device identity, capabilities, live reads, writes, and post-write verification are deterministic and evidence-backed.
- **Current-turn evidence:** live/historical factual claims must come from this request's tool evidence, not prior assistant conclusions.
- **Fail-closed synthesis:** deterministic validators localize contradictions or unsupported causal/prescriptive claims without replacing supported analysis.
- **Bounded investigation:** history, logs, scheduler reads, and causal expansion use explicit limits and stronger evidence outranks broad fan-out.
- **Privacy-safe observability:** request metrics use a fixed vocabulary and do not expose prompts, credentials, session IDs, device names, or tool arguments as metric dimensions.

### Performance analysis contract

For broad Hubitat performance/optimisation requests, HomeBrain treats resource/performance statistics as measured findings and logs as observations.

A broad performance request that also asks for recommendations uses:

1. Host-planned `hub_get_metrics` for current hub resources and alerts.
2. Host-planned `hub_get_performance_stats` for measured app/device execution statistics.
3. One bounded recent `hub_get_logs` window (`30m`, maximum `100` rows).
4. If numeric performance rows cross internal retrieval-policy thresholds, at most one device-scoped and one app-scoped `hub_get_logs` read (`since=6h`, `limit=120`). The exact triggering stats row is retained with that adaptive receipt. These thresholds choose evidence; they are not health/severity classifications.
5. `hub_get_jobs` only when the user's objective explicitly asks about scheduler/job/polling cadence.
6. Zero exploratory pre-synthesis provider rounds for the normal broad performance+recommendation path.
7. One final performance provider synthesis pass; deterministic validators handle localized repairs without another cloud-model round.

The final answer must keep these distinctions explicit:

- High execution time, call volume, `pctTotal`, `pctBusy` and `stateSize` are measured values; they do not establish an implementation mechanism by themselves.
- Adaptive diagnostic target identity comes from the exact triggering performance-stat row. A later model description never remaps that ID/name.
- Explicit timeout/connectivity/failure evidence may support a calibrated connectivity/failure hypothesis. Explicit very-long method-duration WARNs may support a calibrated stalled/long-running-operation hypothesis. Neither proves the exact implementation mechanism or downstream impact.
- Repeated neutral activity does not prove causality; sparse/no observations remain unresolved.
- A successful target-scoped diagnostic read must never be described as "no target-scoped evidence" merely because the model changed label wording.
- Host-derived timing is authoritative. `regular_cadence`, `irregular_intervals` and `observed_gap` remain distinct, and timing source/signal plus numeric interval values come from the same host timing record.
- Exact event/update counts require an explicit tool/host count. A one-second cluster is not a recurring events-per-second rate and is not proof of literal simultaneity.
- Same-second clustering alone does not justify staggering/offsetting or changing reporting frequency; inspect configuration first to learn what is expected and configurable.
- Literal WARN/ERROR observations remain literal observations through final validation; generic semantic repair may append a causal boundary but must not overwrite the observed warning text.
- Configuration/implementation evidence is required before prescribing exact polling, reporting, retry, timeout, blocking-model or scheduler changes.
- A threshold label in an app name plus an `Event:` payload proves event processing/logging, not that the threshold condition evaluated true or an alert action fired.
- Empty/no-active health alerts support "no active alert", not categorical "very healthy" or "no optimisation needed" conclusions.

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

## System Check and Pushover

`HealthAuditService` performs read-only Hub/MCP/device/battery/automation/log health checks and stores the latest snapshot under `/data`. The dashboard exposes the latest result, new/resolved findings, a manual **Run system check now** action, and **Send report to Pushover** when Pushover is configured.

## Home Assistant TTS

HomeBrain can use the Home Assistant mobile-app notify/TTS path when browser speech is unavailable. Leave `ha_tts_notify_service` empty when there is only one `notify.mobile_app_*` target; otherwise configure the desired service explicitly.

## Safety and evidence boundaries

Sensitive writes use the structured confirmation policy. Confirmed actions are revalidated before execution and mutation success is reported only from verified tool evidence.

For history and causal questions, HomeBrain separates observed state/event history, direct command or execution provenance, configuration/topology evidence, temporal correlation, hypotheses and unresolved gaps. Configuration alone does not prove a specific automation caused a transition. Temporal correlation alone does not prove who or what initiated an event.

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

## Development and validation

The blocking test/release gates include Python compilation, architecture-module-map drift detection, the full pytest release gate, repository/version alignment, import analysis, release-assurance contracts, and a container smoke build.

Runtime modules under `hubitat-mcp-ai/rootfs/app/` must be documented in `docs/RUNTIME-MODULE-MAP.md`. Any runtime change requires a new add-on version and matching release notes.

For release-by-release technical history, use [CHANGELOG-INDEX.md](CHANGELOG-INDEX.md).