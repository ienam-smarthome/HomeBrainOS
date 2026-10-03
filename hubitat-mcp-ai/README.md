# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.16.96**.

## Architecture

0.16.96 makes one-time Rule Machine scheduling use the authoritative Hubitat location timezone before converting relative or bare-clock requests into dated `atTime` values. This fixes UTC-container drift such as a BST request at 09:42 being authored for 08:42. The existing `HubTimezoneResolver` supplies an IANA timezone and therefore follows GMT/BST and other DST transitions without a hard-coded offset. Confirmation wording also now states that HomeBrain configured the future self-pause action rather than claiming the rule had already fired and paused.

0.16.95 adds an explicit, empty-by-default `internet_control_aliases_json` map for Internet control surfaces that intentionally are not assigned to the Hubitat `Internet` room. A configured alias such as `{'Google TV':'Block Media-Google-TV-Streamer'}` is treated as an exact deterministic identity binding only for scheduled Internet access; HomeBrain still verifies the selected device exposes the real `on`/`off` Switch command before proposing Rule Machine JSON. No global `Block ...` prefix heuristic is introduced, ordinary TV power control is unchanged, and room-based Internet controls remain the default authoritative path.

0.16.94 aligns scheduled Internet access with the authoritative 0.16.89 switch semantics. Devices in the Hubitat `Internet` room are ordinary Switch controls: `off` means Internet blocked and `on` means Internet allowed. RuleAuthoringService now scopes semantic `block`/`allow` target matching to that room first, then verifies and schedules the real `off`/`on` command on the selected control surface. A similarly named normal device such as `Google TV Streamer (ADB)` therefore cannot steal the request, and HomeBrain no longer requires synthetic `blockInternet`/`allowInternet` commands that these controls do not advertise. Ordinary TV power schedules remain unchanged.

0.16.93 fixes capability-grounded target resolution when a narrow exact-name lookup finds the wrong control surface. When a caller supplies `required_command`, targeted candidates are now strictly narrowed to devices that advertise that command; if none do, HomeBrain uses the existing authoritative identity fallback rather than accepting an exact-but-incapable device. This lets scheduled Internet requests such as `block Google-TV-Streamer after 1 min` select `Block Media-Google-TV-Streamer` instead of the similarly named `Google TV Streamer (ADB)`, while ordinary name resolution without a required command is unchanged.

0.16.92 closes the remaining scheduled-Internet routing gap exposed by the 0.16.91 live proof. The immediate Internet-access parser now uses the same future/recurring timing guard as ordinary device control, so `after 1 min`, `in 30 mins`, `2 hours later`, absolute clock schedules, and recurring requests cannot be swallowed into the Internet device name. Those requests remain available to the deterministic `RuleAuthoringService`, while a bare immediate `block X` / `allow X` request retains the existing fast path. No Hubitat command semantics are inverted.

0.16.91 extends the deterministic `RuleAuthoringService` to relative one-time schedules. Plain requests such as `block X after 1 minute`, `turn on X in 30 mins`, and `turn off X 2 hours later` are converted directly into a dated `Certain Time (and optional date)` trigger using the host clock, then use the existing one-time self-pause safeguard. They do not ask the model to invent a Rule Machine Delay action, so a relative delay cannot be double-applied or rejected by the action-list validator. Duration wording such as `turn on X for 30 minutes` remains outside this grammar and is not reinterpreted as a delayed start. Immediate controls and the 0.16.89 Internet access-state mapping remain unchanged.

0.16.90 protects scheduled routine controls from the immediate semantic compatibility path. A command containing a valid future clock, recurrence, or duration qualifier is no longer compiled into a `timing=now` switch action before Rule Authoring can inspect it. Plain clock schedules such as `turn on X at 10pm` therefore continue to the existing deterministic `RuleAuthoringService`; immediate controls remain fast and unchanged. The guard uses the shared clock parser and deliberately preserves established level wording such as `set lamp at 50%` as an immediate brightness command. This is a routing correction only: it does not change the 0.16.89 Internet access-state semantics or invert any Hubitat on/off command.

0.16.89 gives switches assigned to the authoritative Hubitat `Internet` room/group explicit access-state semantics without changing their control behavior. For those devices only, `switch=on` means **Internet allowed** and `switch=off` means **Internet blocked**. Active switch snapshots retain the literal Hubitat state for compatibility while adding deterministic presentation metadata, and the synthesis policy requires access wording rather than interpreting a `Block ...` label as blocking being active. Room/group membership, not the device-name prefix, establishes this meaning; no extra Hubitat read or model round is added.

0.16.88 tightens device-freshness semantics so activity age is not silently promoted into a failure claim. Old `lastActivity`/activity timestamps remain neutral observations unless current evidence provides an explicit freshness expectation, while direct offline/unreachable health evidence remains actionable. Similar timestamp clusters remain diagnostic context rather than inferred integration interruptions, and the synthesis contract enforces the same evidence boundary after model generation.

0.16.87 consolidates the adaptive evidence-use path on top of 0.16.86 without expanding retrieval or adding model rounds. Each adaptive device/app diagnostic receipt now preserves the exact `hub_get_performance_stats` row that selected the target, including identity and selection rationale. A final current-turn evidence-use guard keeps explicit long-running-operation evidence separate from unproven network/connectivity causes, preserves literal WARN/ERROR observations through generic semantic repairs, and keeps same-second cluster guidance inspection-first unless configuration evidence proves a safe tuning action.

0.16.86 keeps the accepted host-planned/adaptive performance architecture unchanged and closes two evidence-intelligence gaps exposed by the 0.16.85 live proof. Hubitat long-call WARN durations may contain thousands separators such as `166,621ms`; these are now normalized and classified as real `diagnostic_signal` evidence instead of falling through to neutral observations. Adaptive busy-share eligibility also uses a 15% retrieval threshold with the existing 20% value retained as a stronger priority bonus, preventing a sustained near-threshold busy leader from being excluded by a hard cutoff while an isolated high-average row consumes the only app/device diagnostic slot.

The broad performance path remains bounded: a quiet case uses metrics, performance stats and one bounded recent-log read; a strong-outlier case may add at most one device-scoped and one app-scoped six-hour diagnostic log read. The normal path still uses zero exploratory agent model rounds and one final synthesis round. Retrieval thresholds choose evidence only; they are not user-facing health/severity labels.

0.16.85 consolidated the presentation-integrity boundary. The diagnostic validator recognizes child fields by semantic role instead of exact model labels, successful scoped evidence remains authoritative, source/signal timing facts are rendered atomically from one host record, and the older shape-dependent diagnostic rewrite is no longer chained after the format-independent validator.

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
4. If numeric performance rows cross internal retrieval-policy thresholds, at most one device-scoped and one app-scoped `hub_get_logs` read (`since=6h`, `limit=120`). Near-threshold busy-share leaders may enter the bounded ranking before the stronger priority threshold; these thresholds choose evidence and are not health/severity classifications.
5. `hub_get_jobs` only when the user's objective explicitly asks about scheduler/job/polling cadence.
6. Zero exploratory pre-synthesis provider rounds for the normal broad performance+recommendation path.
7. One final performance provider synthesis pass; deterministic validators handle localized repairs without another cloud-model round.

The final answer must keep these distinctions explicit:

- High execution time, call volume, `pctTotal`, `pctBusy` and `stateSize` are measured values; they do not establish an implementation mechanism by themselves.
- Adaptive diagnostic evidence is classified before a mechanism conclusion is accepted. Explicit timeout/connectivity/failure evidence or directly observed very long calls may support a calibrated hypothesis; repeated neutral activity does not prove causality; sparse/no observations remain unresolved.
- Hubitat millisecond durations may be comma-formatted; normalization must not discard an otherwise explicit long-call diagnostic signal.
- Adaptive receipts retain the exact performance-stat row that selected the scoped target; target identity and selection rationale must not be reconstructed from prose.
- Long-running operation evidence does not by itself establish a network/connectivity cause, API-latency cause, worker-thread blocking, or user-visible delay.
- A successful target-scoped diagnostic read must never be described as "no target-scoped evidence" merely because the model changed label wording.
- Host-derived timing is authoritative. `regular_cadence`, `irregular_intervals` and `observed_gap` must remain distinct, and timing source/signal plus numeric interval values must come from the same host timing record.
- Exact event/update counts require an explicit tool/host count. A one-second cluster is not a recurring events-per-second rate and is not proof of literal simultaneity.
- Literal WARN/ERROR observations remain observations; they do not automatically explain longer-window performance totals and must not be erased by generic semantic repair.
- Configuration/implementation evidence is required before prescribing exact polling, reporting, retry, timeout, blocking-model or scheduler changes. Same-second clustering alone does not prove that staggering or frequency changes are configurable, necessary, or performance-improving.
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