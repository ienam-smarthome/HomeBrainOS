# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.16.71**.

## Architecture

0.16.71 keeps the 0.16.70 single-provider-pass performance finalization and request-local normalized evidence packet unchanged. Broad performance requests therefore retain the four-read evidence path and normally three total model rounds when the original agent uses two rounds.

The performance semantic guard is now Markdown-aware: prose lines, bullets, and Markdown table cells are repaired independently so deterministic grounding corrections cannot consume adjacent table columns or recommendation rows. The guard also covers the exact 0.16.70 live overreach: scheduler-to-CPU/user-impact claims, thread-blocking/stall mechanisms, activity-to-overhead claims, database “normal limits” without a current-turn threshold, dramatic causal headings, and primary-cause wording not established by the measured evidence.

Z-Wave repair recommendations are now gated on Z-Wave-specific diagnostic evidence such as node, route, topology, mesh, or repair-status detail. A generic `zwHealthy:false` observation can justify inspection, but does not by itself establish that running a Z-Wave repair is required.

The request still reuses the normalized, privacy-redacted `ToolExecutor` payloads for `hub_get_metrics`, `hub_get_performance_stats`, `hub_get_jobs`, and `hub_get_logs`, so measured values remain available without duplicate Hubitat reads and database-size compatibility normalization remains intact. If the original reasoning turn did not obtain recent logs, the finalizer performs one bounded `hub_get_logs` read (`since=30m`, `limit=100`) before synthesis.

The direct production wiring introduced in 0.16.67 remains unchanged: `_agent_request()` passes returned unified-agent outcomes through `performance_api_finalizer.finalize_performance_api_outcome()` before `/api/ask` or `/api/chat` serializes them. Turns without successful performance-stat evidence are returned unchanged.

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

1. `hub_get_metrics` for current hub resources and alerts.
2. `hub_get_performance_stats` for measured app/device execution statistics.
3. One bounded recent `hub_get_logs` window (`30m`, maximum `100` rows) before final synthesis.
4. Scheduler/job evidence only when job count or cadence materially affects a recommendation.
5. The original bounded, normalized, privacy-redacted tool payloads for final synthesis rather than duplicate API snapshot reads.
6. One final performance provider synthesis pass; deterministic validators handle localized repairs without another cloud-model round.
7. Configuration/implementation evidence before prescribing exact polling, reporting, retry, timeout, staggering, or scheduler interval changes.
8. Z-Wave-specific diagnostic evidence before recommending a Z-Wave repair.

The final answer must keep these distinctions explicit:

- High execution time or call volume is measured; an implementation mechanism is only a hypothesis unless directly established.
- A scheduled-job list proves returned jobs/cadence, not CPU spikes, CPU load, UI stuttering, delayed automations, or hub overhead by itself.
- Database size is reported numerically in MB; qualitative labels such as normal/small/large require a defined current-turn threshold.
- Frequent device reporting proves activity, not material hub overhead or a performance cause by itself.
- Recent connectivity/error logs are observations; they do not by themselves prove overall hub instability.
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
ollama_direct_cloud_base_url: https://ollama.com
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