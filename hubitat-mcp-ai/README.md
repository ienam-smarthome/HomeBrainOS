# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.16.133**.

## Architecture

v0.16.133 adds a final consistency check for performance investigations: failed reads against deleted app IDs 2954/2597 are treated as requests that need caller provenance, not automatic stale MCP Rule Server dependencies or cleanup opportunities, unless actual configuration was inspected. A scoped log read returning zero rows is explicitly reported as an observed absence in that sample rather than falsely described as no tool read. Performance optimisations remain read-only and require independently verified configuration and dependency evidence before recommending changes.

0.16.132 adds an evidence coverage summary to broad whole-hub efficiency reports. These reports now disclose top-N performance limits, capped recent logs, the difference between shared job timestamps and actual contention, and the fact that the existing performance planner does not independently inspect every app/rule dependency. It also catches additional variants of model-generated recommendations that incorrectly infer MCP Rule Server persistent references to deleted apps from failed lookup requests. All operations remain read-only.

v0.16.131 displays model-authored Markdown tables as native, safely constructed, horizontally scrollable HTML tables in the Home Assistant ingress UI. Numbered inspection steps are rendered as ordered lists. Evidence repair also ties generic timing-only reporting recommendations to uniquely matching measured source/signal identities where possible, and avoids attributing failed queries against deleted apps to permanent MCP Rule Server configuration when no such configuration was read. Hubitat configuration remains unchanged.


HomeBrain 0.16.130 prioritizes a whole-hub optimisation intent over the narrower health-only audit when the user asks to review all devices/apps/rules/logs for efficiency. Scheduled-job evidence is requested automatically for these optimisation reviews. A Markdown presentation repair keeps recommendation rows intact when deterministic reasoning guards insert qualifications. Evidence instructions explicitly distinguish failed MCP lookup requests to deleted apps from persistent internal Rule Server dependencies. This remains a read-only, evidence-limited inspection; results must not imply guaranteed savings or silently change Hubitat configurations.


0.16.129 broadens investigative reasoning to integration/polling failure questions. A sampled/capped log window cannot establish no past outages; model conclusions receive a final evidence check. Optional AI audit commentary now ends at a coherent text boundary. If SenseCap D1 is deliberately disconnected, set \`sensecap_d1_intentionally_powered_off: true\` in add-on options so reports classify its connectivity warnings as expected. This option is per-user and is **not** enabled globally.


In 0.16.128, HomeBrain distinguishes fast inventory questions from runtime automation troubleshooting. Targeted rule failures get a bounded investigative model loop with evidence-first guidance; broad automation failures reuse the comprehensive read-only system audit with a focused model synthesis (option: `automation_diagnostic_ai_analysis_enabled`, default true, disable to avoid additional AI latency). `comprehensive_audit_ai_analysis_enabled` still separately controls generic full-system audit AI synthesis. "Active" in returned automation rows is a normalized *configuration* category, not verification that the rule executed.


0.16.127 reconciles duplicate installed-app and Rule Machine rows by canonical Hubitat ID, preventing inflated automation counts while preserving source provenance and stronger broken-state markers. This is read-only and does not verify runtime rule execution.

0.16.126 corrects deterministic Rule Machine discovery by invoking the existing supported `hub_read_rules` wrapper with `hub_list_rules` and empty args, matching rule authoring. It qualifies discovered rows as incomplete until independently validated, treats upstream success=false as a failed inventory read, and distinguishes transport success from substantive evidence. No Hubitat mutations are performed.

0.16.125 removes the repeated app-count line from the collapsible inventory UI and clarifies that empty structured Rule Machine data from `hub_read_rules` does not mean zero rules exist. It preserves read-only behaviour and requires independent verification of Rule Machine coverage.

0.16.124 provides a brief configuration-only summary for requests to show broken automations, avoiding the full healthy app list. It qualifies empty Rule Machine tool results as incomplete coverage, distinguishes tool failure, preserves exact IDs for flagged entries, and does not equate enabled apps with verified runtime success. Other automation inventory requests retain the detailed presentation.

0.16.123 clarifies the fast automation-status inventory: it separates app and Rule Machine population counts, keeps legacy status headings and summary wording, displays available app IDs, and warns that enablement or a Hubitat broken-name marker is not proof of successful runtime execution. It recommends the existing comprehensive read-only System Check for runtime faults. This release does not yet add automatic per-action target verification or retire any Roborock rules.

0.16.122 improves the fresh System Check device inventory without reusing stale identity state or weakening online evidence. It requests a lean detailed device projection (identity, capabilities, attributes, last activity) that excludes commands and does not replace the command-capable shared cache. When the gateway reports a reliable total and page boundaries, remaining pages may be fetched concurrently through the existing MCP concurrency gate. Incomplete/mismatched pages and projection errors fall back to the original fully refreshed detailed manifest. The audit separately measures fresh device data acquisition and local health classification and reports the source and verified projection status. Live performance improvement depends on upstream pagination capabilities and has not been measured in production.


0.16.121 adds an opt-in Home Assistant add-on option `sensecap_d1_intentionally_powered_off` (default `false`). Set this to `true` while the SenseCap D1 is deliberately without power, and return it to `false` when the device is powered on. The comprehensive report labels this as user-supplied context, not an MCP-verified condition; existing warnings remain visible and repeated SenseCap scoped reads are suppressed while the option is active.

The release also groups slow `/logs/json` warnings with different numerical durations into one diagnostic pattern with observed min/max milliseconds; measures System Check stages independently (MCP health, tool inventory, device inventory, automations, initial logs, and aggregation); and adds an opt-in `comprehensive_audit_ai_analysis_enabled` option (default `false`) for one short, read-only, tool-free Gemma advisory limited to evidence-based hypotheses. The deterministic source report remains authoritative and all Hubitat write confirmation safeguards remain unchanged.


0.16.120 adds conservative log time-integrity checks: timezone-less and apparent future-dated log entries cannot establish UTC incident chronology or SenseCap recovery. Sources whose timezone metadata is absent remain unverified rather than receiving an assumed one-hour BST correction. Comprehensive audits now preserve exact device label/ID pairs for unambiguous ADB incident targeting and prioritise fresh observed failures over repeatedly querying unchanged offline status. They also provide bounded Zigbee metering and ADB follow-up guidance without inferring root causes. All diagnostic reads remain non-mutating.


0.16.119 consolidates additional scoped WARN/ERROR patterns separately from the main health-alert count, with occurrence counts, available timestamp ranges, and no inference that each row is a distinct outage. It corrects the active v3 offline-device classification (rather than its overridden frozen-core variant) to retain actual source attribute, battery and last activity when supplied. SenseCap D1 follow-ups distinguish live-push and config-push failures without claiming a common cause or recovery, and scoped log receipts show wall-clock latency. After three or more scoped log reads, the redundant unsupported historical extra request is skipped with an explicit coverage disclaimer. The audit remains read-only.


0.16.118 follows up explicit offline devices by their structured inventory IDs, shows the actual offline-status attribute, battery and last-activity evidence when supplied, and makes bounded device-scoped log requests before performance-only leads. It also retains prior SenseCap D1 HTTP 408 warnings as follow-up candidates and distinguishes explicit timestamped successful live-push records from mere absence of errors. The historical log evidence receipts now separately describe tool success and whether any returned records substantiate the requested window; zero rows cannot confirm coverage. The audit remains strictly read-only and neither identifies untraced third-party callers nor executes repairs.


0.16.117 investigates health-audit-confirmed log faults ahead of generic performance outliers (up to four bounded, deduplicated scoped reads), even when performance statistics are unavailable. It verifies returned historical-log timestamp boundaries rather than treating a successful empty response as proof of historical coverage, adds explicit SenseCap D1 live-push recovery checks, captures MCP device-list schema-validation evidence without inventing the requesting caller, and labels unmatched performance-device IDs. No automatic writes or AI synthesis are included.


0.16.116 prevents INFO/DEBUG/TRACE automation messages from becoming false log-error alerts, extracts full MCP Rule Server entry messages before truncation, separates independent alert signals from unverified *BROKEN* name markers in audit headlines, adds a single bounded older-log sample when 24h logs hit the 200-row limit, and cross-checks unmatched performance-device IDs against complete live-context inventory when available. All audit activity stays read-only and no Gemma reasoning or unattended repair is added.


0.16.115 differentiates automation *BROKEN* name markers from verified failure signals in chat reports, reconciles source-specific performance/device populations by exact sampled IDs, marks 200-row log-sample saturation, extracts concise MCP structured-error messages, and emits per-source evidence receipts and targeted read-only repair checks. This does not enable unattended Hubitat changes or add a model synthesis round.


0.16.114 routes broad chat requests for hub logs, device/app statistics and issues through the existing read-only System Check (device health, automations and grouped log warnings), then adds bounded performance leaders and targeted log follow-ups. Quiet event-driven devices are shown as observations, not automatically declared offline. No changes to Hubitat devices, apps or rules are performed by this report.


0.16.113 canonicalises model-authored temporal-history interval tables whenever deterministic `observedIntervals` are available on an otherwise safe duration answer. The first On/Off/Duration table is replaced with HomeBrain's exact 24-hour clock and `sec`/`min` rendering, preventing model rounding such as `170s -> 3m` while preserving surrounding prose and unrelated Markdown tables.

0.16.112 refines temporal-history presentation for complete semantic windows. When the retained page reaches the requested window start, HomeBrain no longer appends routine source-integrity boilerplate after an already qualified duration such as `about 3 minutes`. It instead surfaces practical scope/context such as the window start and latest recorded state/event. Strong missing-history warnings remain when retained history is known not to reach the requested start. `Currently on/off` wording is reserved for separate live-state evidence; deterministic history fallback says `latest recorded state`.

0.16.111 adds `this afternoon` as a first-class deterministic history window. It resolves to 12:00–18:00 in the authoritative Hubitat local timezone, capped at the current time while the afternoon is in progress. Explicit clock ranges mentioning `this afternoon` are anchored to today. This prevents a rolling `hours_back` fetch from leaking late-morning sessions into an answer labelled as afternoon.

0.16.110 fixes duplicate temporal-history presentation when a model draft already contains an interval table and the deterministic history safety guard inserts its canonical table. The repair path now keeps the first canonical history table, removes only later duplicate On/Off/Duration blocks and their matching retention/completeness note, and preserves unrelated analysis paragraphs or tables.

0.16.109 makes user-facing temporal durations more natural without changing stored/debug units: summary prose uses words such as `10 minutes` and `1 hour 44 minutes`, while interval tables use readable compact units such as `5 min 36 sec`. It also removes a redundant second unverified-stream estimate caveat when the deterministic history guard has already supplied the complete uncertainty note.

0.16.108 improves temporal-history answer presentation without changing history arithmetic or evidence semantics. Duration questions now prefer a concise result followed by a compact Markdown interval table and a short caveat. The deterministic duration guard uses the same structured presentation when it must repair a model answer, including retained-page boundary gaps and leading unmatched inactive events, so safety corrections no longer collapse a readable answer into one dense paragraph.

0.16.107 fixes semantic history-window coverage when Hubitat returns a retained native event list shorter than HomeBrain's requested row limit. A short retained list is no longer treated as proof that the requested window start was reached; HomeBrain now requires an event timestamp at or before that boundary. When a duration answer is based on a retained page that does not reach the window start, final synthesis explicitly says that earlier in-window transitions may be missing while preserving the existing unverified-stream estimate semantics.

0.16.106 closes a final recorded-event wording gap in synthesis validation. When a model lists timestamps that are directly present in returned device-event rows and then refers back to them with the deictic phrase `These are estimates based on recorded events`, HomeBrain now repairs that wording to preserve the timestamps as recorded observations. Source-integrity uncertainty still applies to completeness and continuity, and derived duration totals may still be described as estimates when the event stream is unverified.

0.16.105 preserves semantic history intent end-to-end. Parsed time windows such as `this morning` are copied into deterministic history-tool arguments even when the model already supplied the state attribute, making the resolved `timeWindow` auditable instead of relying only on request-local context. Final synthesis now receives the original user objective: explicit duration questions cannot silently lose the deterministic temporal total, and timestamps that are actually present in returned event rows are described as recorded observations rather than estimates. Source-integrity caveats still apply to completeness, continuity, and exact physical-history claims.

0.16.104 fixes deterministic device-history duration analysis when a caller uses a small presentation limit such as `limit: 1`. The service still returns only the requested newest event rows, but interval arithmetic now uses every matching state row from the authoritative fetched page. This prevents cases where `analysisEventCount` reports many switch events while `intervalCount` and duration incorrectly collapse to zero. Temporal source-integrity caveats and bounded presentation remain unchanged.

0.16.103 fixes open temporal-history semantics. A definite observed active transition with no later inactive row now exposes its elapsed open span separately from completed-pair totals, so an ON event is no longer collapsed into a misleading `0s` / “No bounded on interval” answer. Ongoing-window analysis also distinguishes a transition observed inside the window from a verified active state that already existed when the requested window began. Event-stream completeness remains a separate caveat: observed open spans are not promoted to proof of uninterrupted physical state or an exact total when source integrity is unverified.

0.16.101 fixes one-time cleanup rule discovery on live MCP servers. Cleanup now calls the Rule Machine gateway explicitly as `hub_read_rules -> hub_list_rules`, requires an authoritative `rules` collection before considering any deletion, and extracts only rule identity/name fields for the strict `(One-time YYYY-MM-DD HH:MM)` eligibility check. Missing or malformed list structure fails closed instead of being reported as a successful zero-rule scan.

0.16.100 makes one-time-rule cleanup observable and manually testable. HomeBrain exposes the effective scheduler time, next run, last run, last trigger, last result and last error; the Web UI adds a guarded ‘Run cleanup now’ control and deletion details. Scheduler start/next-run/completion events are logged explicitly. Automatic cleanup remains strict and Hubitat-local, and there is still no destructive startup catch-up.

0.16.99 aligns immediate Internet block/unblock with the authoritative Internet-room Switch semantics already used by scheduled control. Semantic `blockInternet`/`allowInternet` intent is now compiled to real `off`/`on`, target resolution stays inside the Hubitat `Internet` room, natural names such as `M6 Ultra PC` use the same conservative room-local token matching, and verification waits for literal `switch=off/on`. The model and synthetic Internet commands are no longer involved in this immediate path.

0.16.98 keeps scheduled Internet target resolution authoritative to the Hubitat `Internet` room while making that room-local identity match tolerant of natural token order and compact model labels. For example, `M6 Ultra PC` deterministically matches `Block PC-NucBox-M6Ultra` only when that is the unique Internet-group token-subset match; ambiguous controls still fail closed. The path now reuses the longer-lived complete identity cache before refreshing the detailed device manifest, avoiding unnecessary slow refreshes when structural identity is already fresh. Global device matching, Internet `on`/`off` semantics, scheduler grammar, and one-time cleanup are unchanged.

0.16.97 gives HomeBrain-generated one-time Rule Machine schedules a bounded lifecycle. A dedicated background scheduler runs at 01:00 Hubitat local time by default and soft-deletes only expired rules whose names exactly match the HomeBrain `(One-time YYYY-MM-DD HH:MM)` convention, after a 10-minute safety grace period. Deletes use `hub_delete_native_app` with `force=false` and `confirm=true`; a failed list read deletes nothing and an individual failure does not stop later candidates. Newly created one-time rules no longer append the unreliable self-pause action.

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
4. If numeric performance rows cross internal retrieval-policy thresholds, at most one device-scoped and one app-scoped six-hour diagnostic log read (`since=6h`, `limit=120`). Near-threshold busy-share leaders may enter the bounded ranking before the stronger priority threshold; these thresholds choose evidence and are not health/severity classifications.
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