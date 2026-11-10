# Hubitat MCP AI v2 — native MCP client

Standalone experimental Home Assistant add-on, version **2.0.0-alpha.36**. V2 has its own runtime and data; it does not load v1 routers, causal planners, incident-specific patches, answer rewriting, historical journal or benchmark pipeline. V1 remains separate.

## Alpha.36 — negative-evidence and interval-continuity reasoning (10 Nov 2026)

A new, domain-neutral model skill section distinguishes **point readings** from assertions about an entire interval and **plausible explanations** from an excluded alternative. Following first-answer evaluations across unrelated controller and power-telemetry incidents, the agent is guided to ask whether a different event could have occurred inside unobserved gaps while all returned MCP receipts stayed exactly the same. A later successful report does not prove continuous connectivity or supply before that report; a currently-ON control state does not guarantee that a load received power continuously; an empty bounded command history does not prove that no command occurred. The guidance also preserves the converse: when an event-specific trigger, execution trace and result truly discriminate between causes, state the verified cause without reflexive uncertainty.

This is a **model-owned evidence test**, not a deterministic validator, hardcoded device exception, extra tool round, automatic evidence fetch, answer rewrite or new access control. The model can select proportionate read-only discriminating evidence such as actual historical state/supply reports where available. The existing native MCP response and Technical JSON receipts are unchanged. Offline regression tests check skill delivery, unchanged source metadata and tool autonomy, and a positive-control answer. **Such tests cannot measure Ollama/Gemma compliance or independent live correctness**; re-evaluate on fresh cross-domain first answers after installing the release.

## Alpha.35 — two taller source-specific incident panels (10 Nov 2026)

- In **Hub Diagnostics → Unified incident timeline → Memory + CPU layout**, choose **2 aligned panels · taller** to allocate approximately **720px chart height on the dashboard** (versus 540px for the three-panel layout), and at least **780px** in the full-page popout. The two plots share the same time axis but have separate Y scales; no automatic interpolation or extra source polling.
- The adjacent **Show two** selector offers **External memory + CPU**, **Native memory + CPU**, or **External + native memory**, so neither memory source needs to be overlaid. The default remains **Separate · 3 aligned panels**, with the previous combined and overlay modes retained.
- Show only the two chosen plot traces and selected-point markers; retain all underlying source records and read-only inspection details regardless of which pair is visible. Source gaps remain unknown, not zero.
- Preserve the layout and pair choice when opening a full-page popout, including selected timestamp and zoom interval. Keyboard inspection and desktop/mobile zoom use the existing code paths.
- Add synthetic UI and Chromium desktop/mobile acceptance checks for each pair, independent geometry, full-page option restoration and unchanged source evidence. No Hubitat or Home Assistant writes; no database migration.

## Alpha.34 — source coverage repair and timeline readability (10 Nov 2026)

- **Data restored to the chart, not changed in SQLite:** the alpha.31 migration to a native five-minute source-time table previously hid earlier legacy collected readings whenever newer native rows existed. The history/timeline now reconciles eligible pre-native collector-time records *before the earliest true native timestamp* with source-time native rows, deduplicates repeated cached polls by native label, and breaks the plotted line when timestamp provenance changes. Read-only queries do not convert old collector receipt times into new source times, create historical measurements, or mutate existing observations.
- **Three-panel default:** external OS free memory, native 5-minute OS free memory and 5-minute CPU load equivalent have separate, aligned panels and independent Y-axis scales; retain optional combined-memory and all-overlaid layouts. The percentage is load average divided by configured core count, not measured utilisation.
- **Explicit coverage:** a separate summary names first/last returned native readings, indicates incomplete earlier intervals and identifies legacy collector-time observations. Blank means unknown, never zero.
- **Point markers:** remove universal dots on every native point and decorations at extrema; show dots only for genuinely isolated one-point segments and the deliberately selected inspection cursor. Extrema remain available in the event list. Nearest-source matching uses time tolerance (three minutes native) instead of arbitrary screen pixels, so zooming does not change evidence classification.
- **Tests:** synthetic mixed-era source reconciliation, duplicate-label exclusion, source-basis break, native CPU percentage, desktop/mobile three-panel geometry, coverage notes, no decorative dots, and popout/zoom compatibility. No network/device writes and no change to the original database schema.

## Alpha.33 — causal inference and temporal evidence discipline (10 Nov 2026)

Based on live first-answer reviews, **source retrieval alone is not proof of why** an action happened. The model now receives a domain-neutral causal-investigation reference in addition to the existing upstream Hubitat MCP skill. Before describing a specific timer, automation, threshold, command chain or other mechanism as *the cause*, it should predict what time and state evidence that mechanism requires; compare that prediction to retrieved timestamps, lookback windows and record limits; consider competing configured paths; and report an unresolved decision when event-specific evidence cannot discriminate.

Important distinctions: command issuer versus state reporter versus downstream listener; configuration at read time versus configuration when a historical event occurred; and an empty bounded history versus proof of a device never changing state. For a claimed simple delay, the model should calculate its implied starting time and **check** whether that event is actually supported, rather than retroactively inventing an unobserved earlier transition.

**Implementation is instruction-only** in the native model's existing `Agent.answer` loop: no new hardcoded device patterns, regular-expression causal classifier, forced source list, automatic extra model round, answer rewriting, device polling or writes. The model still decides which reads matter and how far to investigate. Added offline tests assert prompt inclusion, preserve model-selected tool sequences and check that no new tool operations are inserted. **Green CI is contract validation, not proof the cloud model will reason correctly on every incident**; evaluate on new, varied first answers without modifying the agent for individual incidents.

## Alpha.31 — native memory source reconciliation (10 Nov 2026)

**Root cause:** the external recorder showed frequent OS-memory probes, but the five-minute native CSV read used only its last row. The unified timeline did not plot native OS-memory values, so a transient native peak around a restart could be invisible despite the endpoint exposing it.

Each successful five-minute native fetch now parses every available timestamped CSV row, deduplicates by original label and stores native memory/load in a separate SQLite table with the original label and collector time. The incident timeline plots native memory in purple alongside the independent blue external probes, with native CPU in green. The detailed metrics selector includes native five-minute free OS memory.

The option `external_hub_diagnostics_hub_timezone` defaults to `Europe/London`. Set it to **the time zone configured on your Hubitat hub**, because yearless native `MM-DD HH:MM:SS` labels otherwise cannot be mapped reliably. Rows whose time cannot be resolved are not assigned invented source times. Older saved collector-time records can still appear as an explicitly marked legacy fallback. A source reading that has already expired from Hubitat history cannot be reconstructed.

These are read-only source and visualization changes; no device control, rule changes or causal conclusions. The 9 Nov 22:20 native reading is not independently recovered until a live recorder fetch confirms it.

## Everyday use and live review

Open **Ask / Chat** for normal questions. To request a receipt-backed review, click **Copy for review** after the answer and paste the private packet in your review chat, or choose **Technical details → Download PRIVATE JSON**. Check household data before sharing. Copying is browser-local and no automatic ChatGPT call or device action occurs. Historical labs remain under **Experiments (optional)**. See [live review workflow](../docs/HUBITAT-MCP-AI-V2-LIVE-REVIEW-WORKFLOW.md).

## Alpha.30 — normalised CPU load in Ask/Chat

Hub Diagnostics already shows **native five-minute CPU load equivalent (%)**. Ask/Chat now receives a clearly marked derived interpretation whenever a native memory-history MCP receipt contains `cpuLoad5min` samples: `load / configured_cpu_cores × 100`. The original MCP payload remains unchanged in the receipt. Responses should show both the raw five-minute load and the equivalent percentage, with the original sample time. This is **not measured CPU utilisation**, may exceed 100%, and does not prove load or usage between samples. Both Ask/Chat and the external recorder use the same configurable `external_hub_diagnostics_cpu_cores` setting (default 4), even when external recording is disabled. Verify that number against the hub hardware. No extra hub poll, automatic write, or investigation-specific rule was added.

## Alpha.32 — everyday Speak / read-aloud interface

The Ask/Chat interface has **Speak** to capture an English (UK) voice question using the browser's SpeechRecognition API and submit it through the unchanged v2 Ask route. **Read answer / Stop audio** plays only the most recent model answer; **Read replies aloud** is an optional preference. Voice capture only starts after a user tap. The browser may use an online speech service; this feature does not promise offline recognition. No audio is uploaded to v2 or the MCP server by the UI. Chrome/Edge or other browsers with Web Speech recognition support are required; browsers without support (including common Firefox versions) get a visible explanation and can continue to type.

Answer playback prefers browser speech synthesis, using an English (UK) voice where available. For the Home Assistant Android WebView, optional v1-compatible companion TTS can be enabled explicitly using add-on options `ha_tts_enabled: true` and `ha_tts_notify_service: notify.mobile_app_<your_device>` (optionally `ha_tts_media_stream`). The default is disabled; the service may be auto-discovered only when unambiguous. This sends answer text to Home Assistant's mobile-app notification service, not audio to Hubitat; it requires the add-on supervisor token and correctly configured mobile TTS. A failed native TTS request is reported, not silently attributed to device state. TTS endpoints require the same `X-Homebrain-Request: 1` header as the existing Ask route. No wake-word, always-on mic, new model routing, device permissions, or auto-approval is introduced.

The interface also uses a compact voice toolbar with clear listening, unsupported-browser, playback and privacy feedback, while keeping Copy for review and Technical JSON accessible.

## Architecture and scope

The configured model uses native Ollama-compatible `/api/chat` function calling to discover and operate the connected Hubitat MCP server. V2 presents the full live `tools/list` catalog allowed by that server/token, including read and write tools. There is no frozen HomeBrain tool allowlist, read-only capability filter or handwritten tool schema registry.

- Refresh and paginate the live catalog for each request. Preserve server descriptions, schemas and annotations internally.
- Support gateway schema discovery with empty arguments and invocation with `tool` / `args`, as well as flat catalogs. The server resolves gateway membership and enforces its permissions.
- Validate calls against the live input schema, with no remote schema fetches. For gateway-shaped schemas, reject a selector incorrectly nested inside `args` **or duplicated as `args.tool`**, with an actionable local error; do not silently rewrite it or transmit it to Hubitat. Empty discovery and valid gateway/flat calls remain supported.
- Let the model select tools, follow up on evidence and write its answer. Execute calls sequentially; never automatically retry a tool call whose write outcome may be uncertain.
- Load the unmodified upstream `SKILL.md`, `safety-guide.md` and `rule-patterns.md` from the bundled skill directory. These are guidance; the connected server's live schemas and guides remain authoritative. Native Rule Machine/Visual Rules are preferred for new automations; the patterns reference describes the legacy custom-rule engine.
- Calls carrying `confirm=true` (including nested gateway arguments) pause for an explicit decision in the UI. Approval is bound to one exact pending call and request; stale approvals fail. A declined or timed-out call is not executed. The model cannot manufacture approval by setting the flag. Ordinary requested operations follow upstream device-identity and permission rules.
- Retain credential redaction, request deadlines, per-call timeouts and context transport bounds. There is no fixed model/tool round quota or incident-specific investigation recipe.

**This version can perform writes allowed by your MCP connection.** To run a read-only acceptance test, use an upstream read-only client token or disable the server Write master. V2 does not change hub permissions. Server Read/Write masters, per-client access, Advanced overrides, required backups and confirmation flags remain authoritative. Client confirmation does not override a server refusal.

## Alpha.28 — blinded causal-evidence assessment (evaluation-only)

The **Real-source A/B** tab now defaults to a **causal evidence study** mode requiring 4–10 independently target-checked, genuinely new and uncoached read-only questions (not exposed `hold-..`, `sr-..` or `new-01/02` questions). The operator checks a clear attestation about target/capability/time-scope validation before freezing; the add-on does **not** itself independently verify those target checks. Existing general two-question evaluation remains available by unchecking causal mode.

A causal-mode A/B score requires the original MCP receipts to have been inspected, classification of discriminating-source coverage, and a **review of every definite cause claim** for each answer. Each claim stays in the **private case export** with a human-written short quoted description, a `supported`, `unsupported` or `unverified` verdict and original zero-based receipt indices. A claim rated supported must cite at least one successful original MCP read; such an index alone is **not automatic proof** of causation. If the model correctly declines to infer a cause, the reviewer leaves the definite-claim list empty while still rating causal calibration **0–2**, not n/a. A reviewer cannot score causal calibration a full 2 when marking any definite cause unsupported. Reviews remain blinded and immutable.

The case view and aggregate also report strict **original source-response parity** across arms: shared tool name+argument calls with byte-normalised exact matching payload, same-call/different-response, and calls unique to each arm. The aggregate exposes **only counts and manually attested causal verdict totals**—never claim text, original tool arguments, private receipts, device identities, or hashes. Even identical returned receipts do not independently prove time-window equality, complete retention, actual causality or independent reviewer verification. Do not confuse candidate source-collection ledger metadata with source truth.

**No production behavior changes:** normal Ask/Chat continues to use the previous baseline `Agent`. This milestone does not promote the generic source ledger, change the model's tool selection, enforce a fixed investigation plan or add special-case answers. The same per-arm fresh per-client read-only permission check, upstream read-only tool/leaf filters and explicit operator model/evidence/cloud consent remain mandatory. Alpha.28 itself makes **no model/cloud/hub calls until the operator explicitly requests them** (the separate Check client access button performs one read-only info request). Any run may consume Ollama Cloud credits.

## Alpha.27 — opt-in prospective real-source read-only A/B

The **Real-source A/B** tab is **separate from ordinary Ask**. It prepares **2–10 NEW questions** privately, then compares the unchanged production model-led agent with the experimental generic source-collection ledger variant. A/B assignments are kept hidden until all first answers have been reviewed and scored. The experiment is not proof of improved reasoning by itself.

This study **cannot start a model run without the connected token proving its own read-only grant**. On the tab, click **Check client access**. A fresh `hub_get_info` must include `clientAccess.readEnabled=true` and `clientAccess.writeEnabled=false`. The global `writeEnabled=true` master may remain on for other clients. Missing `clientAccess`, main token, writable client, or unannotated tool blocks the experiment. The runner also uses only upstream tools with `annotations.readOnlyHint=true`, and checks the server's per-client permission again before **each** arm. No write test is attempted.

**To use:** configure a dedicated per-client token (Read ON, Write OFF) privately in the v2 add-on options, restart the add-on, verify its grant, freeze genuinely unseen questions, tick both model/private-evidence consents and cloud-transfer consent if using a remote model, then click **Run blinded read-only pair**. Each arm is a fresh model conversation that selects its own read-only native tools. Both arms incur model inference/possible cloud credit usage. No run is scheduled, and ordinary Ask requests are unaffected.

The study is **memory-only**, so download each case's **PRIVATE JSON** (contains source data) before restarting or deleting the add-on; do not upload or commit the raw source to public GitHub. A privacy-safe aggregate report hides questions, answers and household records. Reviewers score first answers against actual returned receipts; the synthetic `hold-..` and already-exposed `sr-..` cases are NOT fresh holdouts. Because the arms query a live hub sequentially, source state can change between them; matching source snapshots and independent model accuracy are **not automatically verified**. No automatic success judgement, no production candidate promotion.

## Setup

Refresh the HomeBrainOS add-on repository in Home Assistant and install/update **Hubitat MCP AI v2 (Preview)**. Start it manually and use sidebar ingress. After updating an already-open older page, close/reopen and refresh it once. The header should show the installed version. A "read-only pilot" subtitle is an old interface; a missing-request-header 403 requires refreshing that page, not changing MCP permissions. V1 may stay installed.

Configure:
- `hubitat_mcp_url`: exact Streamable HTTP endpoint, including its path.
- `hubitat_mcp_token`: token if not already in the endpoint URL.
- `model_base_url`: Ollama-compatible endpoint, e.g. `https://ollama.com` or your local Ollama address.
- `model_name`: a tool-calling model supported by that endpoint.
- `model_api_key`: required for Ollama Cloud; blank for local Ollama.
- Optional recorder: `external_hub_diagnostics_enabled: true` and `external_hub_diagnostics_hub_url: http://HUB-LAN-IP`. Default probe 30s, retention 30d.

Installation, ingress and live model/MCP acceptance remain pending. Dedicated container CI probes amd64 without live credentials; it does not prove aarch64/armv7 deployment.

## Interface and receipts

Ask/Chat displays the model answer, current tool operation and exact pending confirmation when required. Tool receipts include names, redacted arguments, success, elapsed time and the same bounded/redacted source response delivered to the model. Truncation is explicit. Schema-only gateway responses are labeled `tool_catalog` with `operation_executed: false`, and retain their original source inside the model-facing receipt. Local contract errors are marked as rejected before execution. Credential redaction preserves schema property definitions and JSON syntax, including credential-named parameters; actual credential values and samples are removed. Completed receipts survive later model failures. Receipts are returned to the current browser session; they are not automatically persisted or included in later chat history.

The unchanged v1 external recorder is retained in an independent SQLite file. V2 starts new history; it does not import v1 samples automatically. The AI tool loop does not automatically ingest the recorder database. Diagnostics endpoints and graphs read the local recorder; MCP reads come from the connected server.

## API

- `POST /api/ask`: JSON `{"request_id":"<UUID>","question":"...","history":[]}`. Optional request_id defaults to a generated UUID; supply one to poll or approve. Send header `X-Homebrain-Request: 1` on mutation requests.
- `GET /api/activity/<request_id>`: current operation and pending confirmation.
- `POST /api/activity/<request_id>/confirm`: JSON `{"id":"<pending UUID>","approved":true}` or false, with the same request header. Only a currently pending ID is accepted once.
- `GET /api/status`: configuration status, model and recorder; does not certify live connectivity.
- `GET /api/diagnostics/status`, `/api/diagnostics/history?metric=free_os_mb&hours=24`, `/api/diagnostics/timeline?hours=24`: independent recorder views.

Use Home Assistant ingress; the optional direct port is disabled by default. The custom mutation header prevents ordinary cross-origin forms/scripts from submitting actions; it is not authentication. Keep the direct interface on a trusted network if enabled.

## Validation and acceptance

[PR #1528](https://github.com/ienam-smarthome/HomeBrainOS/pull/1528) reproduces the reported nested-selector/schema-corruption failure on the old code before fixing it. Scripted recovery and schema/privacy tests do not prove real-model answer quality.

Mock protocol tests cover full and paginated catalogs, gateway discovery, flat writes, server refusals, catalog refresh, no automatic write retry, human confirmation/decline/expiry and source receipt retention. CI is necessary engineering evidence, not proof of model reasoning or answer quality.

For first live acceptance use an upstream read-only token and ask:
> Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.

Preserve the first answer and receipts. Compare with v1/Claude/Thaura only on matched evidence, time windows and model settings. Control and automation acceptance require separately authorized test operations; no live writes are performed by CI or repository development.

## Alpha.17 — distinguish discrete returned events from continuous history

Source-reviewed first answers in two independent domains showed useful MCP retrieval but unsupported certainty about unobserved intervals. The existing `client_event_source_scope` sidecar now includes the count of adjacent parseable returned-event timestamps, their largest UTC-normalised gap in seconds, and `can_infer_uninterrupted_state_between_events:false`. These describe returned rows only—not complete historical retention, device downtime, reporting cadence, missing observations, precise threshold crossing, or continuous state. Mixed-attribute results are not proof of per-attribute completeness.

The unchanged original MCP `content` and metadata remain available to the model, which independently chooses native tools and produces the answer. No planner, rewrite, output veto, model extra round, controller-specific rule, permission change or recorder modification is introduced. Alpha.17's actual impact on live first-answer quality is **unmeasured**, pending an uncoached same-question comparison and independent transfer test.

## Upstream and rollback

Skill files are copied unchanged from [kingpanther13/Hubitat-local-MCP-server](https://github.com/kingpanther13/Hubitat-local-MCP-server/tree/98bc7ca2d0f1bd2e2857962292b33d83683bc2b0/agent-skill/hubitat-mcp), commit `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0`, with its MIT license. See `skills/hubitat/UPSTREAM.md`.

Stop the v2 add-on to stop further operations. Uninstalling v2 does not undo device actions or automations already created through MCP. Revert the release to restore the prior client; v1 and its data are untouched.

The answer panel provides **Copy answer** and **Copy technical details**. Technical details retain the original API response and receipts, model, request ID and question, plus browser and server timings. The visible response time includes browser network and waiting time. Copying also supports LAN HTTP where the Clipboard API is unavailable. This UI update does not change prompts, model selection, MCP access or answer generation.

## Alpha.8 — evidence-aware follow-up questions

Alpha.7 sent recent question/answer prose but silently omitted all earlier MCP source receipts. Alpha.8 adds an **ephemeral in-memory server evidence cache** keyed by a cryptographically generated browser-session conversation UUID. Only the server's actual bounded/redacted MCP tool receipts populate it; browser-supplied history cannot insert evidence. For a follow-up, the model receives selected earlier tool names, arguments, result excerpts, source collection times and explicit truncation indicators in addition to the existing conversation prose. **This is prior evidence, not a live snapshot, trusted instruction or permission to act.** Live verification remains required when the user requests current state, device control or checks beyond the earlier source coverage.

The cache is bounded to four turns, ten latest non-catalog tool receipts per turn, 3,200 characters per receipt, approximately 20,000 source characters per follow-up, and 32 concurrent browser conversations. Items expire after 45 minutes of inactivity. No persistent transcript or separate evidence database is created. Restarting the add-on loses the cache; earlier evidence is then re-read as needed. New conversation rotates its UUID and sends a one-time server-side clear request. A prior request's technical JSON download is independent, and the `prior_receipts_used` counter only reports excerpts supplied to the model (not factual correctness). Huge tool results are visibly truncated rather than silently presented as complete.

Alpha.8 leaves the **existing MCP capability and write/confirmation design unchanged**; first-answer evaluation should still use an upstream read-only MCP token. No new v1 planner, model substitution, skill-specific question patch, or recorder modification was introduced.

See `docs/HUBITAT-MCP-AI-V2-ACCEPTANCE.md` for the frozen acceptance protocol. CI exercises synthetic evidence and model stubs, not a real Home Assistant ingress, model comparison or private G06 capture. Install the add-on and collect real first-answer exports before declaring an answer-quality improvement.

## Alpha.9 — complete source index and on-demand prior evidence

A real alpha.8 read-only heating investigation retrieved the main controller's event history, but two follow-ups received only five excerpts from newer sources. The model then falsely stated that no controller history had been retrieved. This is a **source-loss / selection problem**, not evidence that the earlier Hubitat read was absent. The actual user-supplied diagnostic exports remain private.

Alpha.9 separates the compact **source index** from the excerpt budget. Every retained, non-catalog server-origin receipt has a unique opaque ID, original gateway/leaf arguments, success state, collection time, original response size, retention availability, and, when the MCP result contains structured event history, its returned event count and earliest/latest **returned** timestamps. These endpoints describe the retrieved sample, not complete historical coverage. If the index itself exceeds its budget, `source_index_omitted` makes missing items explicit; it never implies that the underlying MCP read was not performed.

A follow-up exposes one **client-owned, read-only** tool, `homebrain_read_prior_evidence(receipt_id, offset?, max_chars?)`, in addition to (not instead of) the connected upstream native MCP catalog. The model can select that tool to retrieve up to 16,000 characters per call from the previous **redacted** model-visible source held locally. An offset/next_offset allows multiple chunks and exact-text reconstruction within the archive boundary. The tool never contacts or mutates Hubitat; it is scoped to the same random browser conversation ID. If the archive was evicted/expired, the index says so and the model must use the native MCP tool, selecting an appropriate historical window to regain coverage. No automatic source replay, question-specific algorithm or v1 planner is introduced.

Limits: four turns, 32 non-catalog source receipts per turn, 3,200-character source previews, approximately 20k characters of source index/previews in initial follow-up context, 320k archived characters per conversation with 90k max per individual receipt, 32 conversations and 45-minute inactivity expiry. Archive eviction retains source index metadata and marks the content unavailable; an oversized source is explicitly flagged. The index and archive live in RAM only, with no persistent history or new API endpoint to fetch the archive directly. The model returns `prior_sources_indexed`, `prior_receipts_used` (number of short excerpts included), and `prior_evidence_reads` (local chunk tool attempts) separately. **None of these counts measures factual correctness.**

The sole client-owned tool is limited to earlier source-data retrieval; all Hubitat reads, writes, native automation and administrative operations remain exposed exclusively through the upstream catalog and its existing permission gates. No changes were made to confirmation or write privileges; use an upstream read-only token for investigative testing. The upstream bundled skill files and external recorder remain untouched.

Installed live alpha.9 reasoning quality is **unverified**. CI tests fake source payloads and mock model tool choices; they do not constitute a real Gemma or G06 replay. Run the acceptance matrix in `docs/HUBITAT-MCP-AI-V2-ACCEPTANCE.md` and export both the first question and the follow-up technical JSON.

## Alpha.10 — general evidence scope and causal uncertainty

The latest alpha.9 read-only investigation reported 11 returned historical events per device from a 48-hour requested window, then labelled platform event retention as the probable cause **without a source that discriminated native retention from endpoint return limits, filtering or reporting gaps**. Direct upstream v5.1.7 source review establishes that `hub_list_device_events` reads the native `/device/eventsJson/{deviceId}` response and then applies filters in the MCP Groovy app. Requesting `hoursBack=48` therefore **does not prove** 48 hours of native events were available. No upstream or hub setting was modified.

Alpha.10 adds a general, domain-independent source-scope sidecar (`client_event_source_scope`) to model-visible MCP responses **only when the returned result actually contains event rows**. It reports returned event count, earliest/latest parseable timestamps, requested lookback and limit, a limit-hit hint (not a guarantee), any upstream truncation metadata, and explicit `false` indicators for causal/retention/completeness inferences that the sampled rows cannot establish. This is **descriptive evidence metadata**, not an automated decision, a claim correction or a history replay. The original redacted MCP `content` and upstream metadata remain intact alongside the new client field; technical JSON and later session memory retain the model-visible source result.

A short generic addition to the existing v2 client skill tells the model to distinguish reported observations, plausible explanations and causes supported by discriminating evidence. It encourages further **read-only** checks where available and explicit uncertainty when evidence cannot distinguish alternatives. It also warns not to project current snapshots onto historical windows. The model still owns its investigation, stopping decision and response. The tool catalog, model configuration, direct MCP tool loop, write permissions/confirmations, external recorder, upstream bundled skill files and v1 remain unchanged. No domain-specific heuristics, new planner, model routing, separate answer-rewriter or extra round/latency mandate was added.

Unit/integration tests cover multiple synthetic event types, zero returned rows, limit-hit flags, mixed time zone offsets, untouched non-event/write results, input immutability and exact model-visible source/technical receipt preservation. **CI passes are not real Gemma evidence-quality acceptance.** For live evaluation, ask a new first-attempt read-only cause question in a different domain (e.g. an offline device or an unexplained hub restart), export technical JSON and check that competing explanations remain unverified until independently distinguished. Do not claim historical retention is proven from the absence of returned rows.

## Alpha.11 — first-call gateway contract accuracy

Installed alpha.10's first-answer hub-reboot test identified the correct 2.5.3.119 update/startup sequence, but required six model rounds. Of five upstream attempts, **three failed** because the model nested the gateway selector in `args`, duplicated it inside leaf arguments, or repeated the same mistake for the diagnostic gateway. The model recovered but paid avoidable time/model-call costs. No live hub state was altered by that read-only test.

Alpha.11 improves **model-facing schema presentation** automatically for any connected MCP tool whose *live* `inputSchema.properties` exposes both `tool` and `args`. It provides an explicit example of the required outer selector/inner leaf-arguments shape, explains `{}` as **catalog discovery only**, and adds field-level descriptions. The model-facing schema marks unexpected top-level fields forbidden because the upstream gateway already rejects them. The gateway leaf enum, existing schema fields, original server catalog and actual MCP validation contracts remain unchanged. **No special-case gateway or leaf names are hard-coded**, and non-gateway tools retain their original presentation.

A second generic preflight rejects `args.tool` for live gateway-shaped schemas **even when the outer `tool` is also provided**. Previously that invalid duplicate could reach the native server and generate an avoidable `isError`. Now it yields a local `MCPContractError` with no `tools/call` request; valid calls are forwarded byte-equivalent as structured JSON and are never silently rewritten or auto-retried. The model may still make an invalid call, so this does not constitute proof of first-call success with Gemma.

This does **not** change MCP permissions, confirmation semantics, source-evidence scope, the source memory, recorded diagnostics, model/provider, or v1. It adds no automatic tool-selection planner, incident-specific code or artificial model-round quota.

**Acceptance:** on a fresh alpha.11 install, ask the same uncoached read-only system-event/reboot investigation and then an unrelated read-only device-history question. Export both initial technical JSON files. Count model rounds, gateway `contract_error`, native `isError`, `tools/call` executions, latency and grounding quality. The target is **zero first-call gateway-shape errors**, but CI can only verify synthetic presentation and preflight protections, not real Gemma compliance. Preserve any failures in the record.

## Alpha.12 — live leaf-parameter awareness, without a planner

A real installed alpha.11 test eliminated gateway selector-placement errors (three to zero) but still sent `hub_get_logs(mode='hubEvents',sortBy='desc')`, which the upstream MCP server rejected because the leaf contract says `sortBy` applies to the device/app runtime-statistics tabs. It also made an unrelated broad recent-log read that took 5.24 seconds. The first answer took 15.44 seconds versus 9.94 seconds on alpha.10 despite fewer model rounds; one matched comparison does not prove a latency trend. Live private JSON is not in this public repository.

Alpha.12 now retrieves the **selected gateway leaf's actual server-advertised `inputSchema` and description** through the gateway's read-only `{}` catalog discovery on its first use. This is generic: the model chooses the gateway and leaf; no fixed map or named-domain logic exists. The client stores the gateway's catalog in memory, with only previously selected leaf schemas added to future model-facing descriptions. Cached definitions are invalidated whenever the connected live `tools/list` catalog changes. A metadata lookup is not a device query or actuation, and `leaf_schema_discoveries` records the additional schema-only requests separately from `tool_calls`.

For selected leaves with a well-formed JSON Schema, the client checks **declared** types, enum, required fields, and other schema constraints **before** the original MCP invocation. Invalid arguments become local `contract_error` receipts and do not execute the native leaf. Valid arguments pass unchanged. Invalid/remote-reference schema definitions are treated as unavailable rather than blocking otherwise permitted server operations; timeout/transport failure during optional discovery likewise leaves the native tool available. There is no automatic retry of any potentially mutating call.

Some upstream constraints, including `sortBy` applying only to certain log modes, are expressed in **field description prose**, not a JSON Schema conditional. The client shows that original prose to the model after retrieving the selected leaf schema; it **does not invent a deterministic mode-specific parser or pretend to reject combinations the native schema allows**. Therefore the first cold-start call may still be rejected by the upstream server when a prose-only restriction is missed. On later model rounds/requests, the cached relevant leaf descriptions are available without new catalog probes. The model can also use native gateway `{}` discovery as before.

A short generic instruction prefers focused, read-only historical sources/time windows over broad unrelated log snapshots. It does not enforce tool selection, invent an automatic investigation plan or claim faster runtime. No new model/provider, separate answer rewriter, question-specific patches, synthetic correction rules, user write permission, confirmation approval, v1 modifications or external recorder changes.

**Acceptance:** run the same first-answer reboot question with read-only permissions and model unchanged, plus an unrelated history question. Compare schema-only lookup count, first-call leaf errors, tool executions, rounds, actual latency and source grounding. The target is fewer native parameter errors and unnecessary log reads; both live quality and runtime remain unverified until the installed alpha.12 run.

## Native flat-tool compatibility evaluation (no v2 runtime change)

The upstream Hubitat MCP Server has a global **Consolidate tools behind category gateways** switch (`useGateways`). Setting it OFF exposes each authorised leaf directly with its native `inputSchema`; ON is the usual gateway mode. V2 already accepts either form through the live catalog and its normal confirmation/permission path. A mock first-call compatibility test and a controlled, read-only A/B acceptance plan were added without changing the alpha.12 runtime. **Do not toggle the live hub automatically**: this server-wide setting changes the catalogs seen by other MCP clients and may require reconnect. See `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md` before any authorised live comparison. Whether flat mode speeds up or improves Gemma is still unknown.

## Alpha.13 — safe inline mathematical display (no model or investigation logic change)

The installed alpha.12 Gemma4 heating answer contained ordinary inline TeX expressions inside Markdown table cells (e.g. `$21.0^\\circ\\text{C}$`, `$22.0 \\rightarrow 21.0^\\circ\\text{C}$`, `$\\sim$09:30:15`), which the small local Markdown renderer displayed literally instead of showing readable units or arrows. This was a **UI renderer defect**, not a Hubitat data or device-command issue. Do not “fix” it by rewriting the saved model answer or imposing heating-specific generation constraints.

Alpha.13 adds an **offline-safe text subset of inline TeX** to the existing answer renderer, including `$...$` and `\\(...\\)` expressions, degree/temperature, arrows, common comparisons, approximations, Greek letters and supported numeric superscripts/subscripts. It applies uniformly to table cells, headings, list items and paragraphs, including supported emphasis. Markdown inline code and fenced code remain literal. Unsupported TeX is rendered **verbatim**, not partially guessed or silently removed. **This is not a complete LaTeX or MathJax/KaTeX engine** (complex fractions, matrices and display equations are not automatically typeset).

Rendering uses **DOM text nodes only** (no `innerHTML`, eval, remote CDN, model API or third-party scripts). The original model `answer` string, chat history, copied answer, raw-answer panel and full technical JSON remain **byte-for-byte as received**; only the displayed view changes. Regression tests exercise literal markup/XSS, both inline delimiters, °C, arrows, subscripts, superscripts, unknown commands, code preservation, clipboard/export and desktop/mobile browser output. The v2 runtime's MCP tools, routing, model choices, source evidence, permissions and confirmations are unchanged.

This UI change requires an add-on version bump to `2.0.0-alpha.13` and reopening/refeshing the Home Assistant ingress page after updating. The version status prevents stale alpha.12 pages from silently masquerading as the new renderer.

**Separate first-answer finding (alpha.12 flat mode):** A historical main thermostat/TRV investigation used eight successful read calls (0 errors), four model rounds and 15.893s browser time. Its core answer was supported: the main thermostat and one room TRV were heating during an overlapping period; no operating-state events appeared for four other room TRVs in the *targeted returned window*. However, `setHeatingSetpoint` **commands** issued near the interval end should not be labeled observed setpoint changes on those other devices. A no-event interval is not proof of continuous idle or complete native retention, and a main-thermostat operating-state-only query cannot verify absence of a setpoint change. This evidence-quality assessment does **not** add any answer rewriting or incident-specific reasoning code.

## Alpha.14 — connect genuine native five-minute load readings

An installed alpha.13 screenshot showed the **Native 5m load** graph as disconnected specks. This is a native-sample presentation defect, not proof that Hubitat reported intermittent CPU or that the JVM halted. The recorder collects external poll rows about every 30 seconds and obtains a *different source* native CPU/Java reading about every five minutes. The source label identifies the same cached native sample repeated through many poll records. On short chart windows the `summarize_history_samples` function previously counted only unique labels in `observed_metric_points`, but still returned **all cached poll rows** in `samples`; most duplicate rows lacked a `diag_segment`, which broke the line into tiny strokes.

Alpha.14 returns **one plotted row per actual unique native sample label** for native metrics (`native_load5`, `native_load_pct`, Java metrics) even below the usual downsampling threshold. It retains `source_sample_count` as the full number of recorder polls, and `observed_metric_points` as the number of independent native observations. This does not resample/interpolate values, invent a native time or erase real outages. External-probe metrics (including free OS memory) retain their original 30-second samples and failure boundaries.

The browser chart draws connected segments *only* where the recorder marked the same reliable segment and the source gap is within the true native 15-minute tolerance; genuine loss or gaps are left disconnected. It adds small point markers, sensible fractional Y-axis labels for low-valued five-minute load averages (no duplicate rounded ticks) and a source count summary. A 24-hour time range can still be empty before the recorder started collecting or during real outages; the graph must not fill that interval artificially. **Native 5m load is a five-minute load average**, not direct CPU-utilisation percent. CPU load equivalent percent is a derived approximation using configured CPU cores and is labeled separately.

**Generic investigation-evidence alignment:** The model's existing skill receives only brief, domain-neutral guidance to scope group-wide conclusions to the actual members, attributes and historical intervals retrieved, and to distinguish commands from observed states. There is no deterministic claim veto, extra mandatory tool query, new provider, model-planner, heating-specific code or change to write authorization. Synthetic tests cover native uniqueness, long-range extrema, true gap boundaries, unchanged OS probe history, desktop/mobile connected plotted points and fractional ticks.

No Hubitat devices, Hubitat MCP server mode, routes, upstream skills, external recorder database or historical entries are changed by this update. Existing add-on SQLite files remain compatible. The new deduplicated chart view is computed from the stored records, so prior native history automatically plots correctly after installing alpha.14. Preserve the previously identified alpha.13 TRV-history limitations as source interpretation, not a dashboard failure.

**Verification:** Update the add-on to `2.0.0-alpha.14`, refresh the sidebar UI and inspect **Hub Diagnostics → Native 5m load** for 1 hour and 24 hours. Within intervals with real native samples, expect continuous line segments with markers and decimal Y ticks. Genuine outages and missing history must remain gaps. The caption should show source readings versus recorder poll rows. Exact live appearance, including any collection gaps, requires installed confirmation rather than synthetic CI alone.

## Alpha.15 — V1-grade diagnostics timeline UX on the independent V2 recorder

The user's side-by-side installed screenshots showed that V2 alpha.14 fixed the native five-minute chart's disconnected dots, **but V1's functional diagnostics remained substantially better**: V1 has synchronized and separately aligned memory/CPU graphs, readable axes, cursor and source timestamp inspection, incident and extrema lists, and useful buttons to investigate a selected point. V2's prior 24-hour single canvas also devoted much of its width to empty time preceding the external recorder's first observations. This is a *presentation/interaction parity* improvement, not a new hub resource probe.

V2 alpha.15 adds a **standalone responsive SVG unified incident timeline**, modeled on V1's useful presentation pattern but **powered only by V2's already-existing `/api/diagnostics/timeline` source**:
- Default **separate but time-aligned memory / 5m CPU panels**, each with its own real Y-axis scale. Optional combined dual-axis view. Desktop SVG displays the full trace; mobile wraps its labeled plot in an accessible horizontally scrollable region.
- Read-only, timestamp-aligned external probe memory, true five-minute native CPU-load equivalent, shaded recorded external connectivity losses, and separately marked confirmed offset-aware `systemStart` events. No invented readings, automatic smoothing or extrapolated causes.
- Source-aware vertical cursor, exact source timestamp/value readouts, keyboard previous/next/home/end navigation, touch inspection, highlighted actual minima/maxima, and a local observed-events list. A reading is shown only when near the selected position; distant samples are labeled **no nearby reading**, not treated as the state at the selected instant.
- Window controls: **1h/6h/24h/3d/7d/30d**, 6h default. **Fit observed data** (default) keeps the chosen request window but zooms the display from the first retained source observation/event; **Full requested range** preserves every blank historical interval and visibly expresses the bounds of data coverage.
- Safe **Inspect selected time** displays a limited locally saved evidence snippet, including nearby confirmed starts and incidents, without hub I/O; **Prepare AI investigation** populates the ordinary Ask / Chat text field with a clear *read-only* investigation prompt, **does not auto-submit or bypass permissions**. Source JSON is linked to the existing same-origin recorder endpoint. There is no fake V1 journal data or nonfunctional V1-only service button.
- Keep and improve the **detailed metric graph** underneath: native/OS/Java/latency choices, readable unit-aware and adaptive Y/X ticks, exact minimum/maximum/latest statistics, real extrema markers, cursor and keyboard sample navigation, and source-provenance readouts. Respects confirmed source segment gaps, with no fabricated intermediate values.

This release uses the **same existing V2 SQLite recorder, endpoints, credentials, retention and MCP tools**, and does not copy the heavyweight V1 backend, its journal, a causal router or incident-specific code. No Hubitat setting, live device, database row, client permissions, model routing or external probe cadence is changed. The overall evidence standard remains that event proximity is not proof of causation.

**Validation:** The Node UI fixture and desktop/mobile Chromium tests cover the split/combined layout, exact source values, extrema/event list, source JSON link, full-vs-fit interval, keyboard selection, pure local inspection and **no network request from AI-question preparation**, alongside existing XSS, model answer copy/export, active-session controls and chart source-gap tests. Only a real installed alpha.15 screenshot can establish subjective visual parity with the user's V1 chart.

## Alpha.16 — native five-minute load shown as a percentage equivalent

In the installed alpha.15 phone screenshot, the **Detailed metric history → Native 5m load** selection showed unscaled load-average units (e.g. `0.60 load`), while the unified timeline immediately above already correctly plotted a derived load-equivalent percentage. The user asked to display native load as a percentage.

The V2 external recorder already provides both independent fields: `native_load5` (unscaled five-minute load average reported by Hubitat) and `native_load_pct` (derived `native_load5 / configured_cpu_cores * 100`, rounded to one decimal place). The percentage **is not actual measured CPU utilisation** and may exceed 100% if runnable demand exceeds the configured core count; the UI never caps it. Example: a native 5m load of **0.60** on **4 configured cores** is **15.0% load equivalent**, not a direct measurement of 15% CPU busy time.

Alpha.16 makes **Native 5m load equivalent (%)** the principal native-load selection within **Detailed metric history**. It retrieves the existing source field `native_load_pct` (no client-side reinterpretation, backfill or SQLite migration), and shows percentage axis ticks, minimum/maximum/latest statistics and exact hovered/selected observed values. The metric legend now explicitly names the selected series; the extra CPU line legend appears only when a second series is actually drawn. The note identifies the percentage calculation and configured CPU-core count from returned source metadata. For auditing source values, a separate **Native 5m load (raw, unscaled)** option remains available; its axis, statistics and readout continue to use `load` rather than `%`.

The **Unified incident timeline**, CPU load-equivalent card, live source cadence, outage markers, native sample de-duplication and all existing raw evidence remain unchanged. This release does not edit the upstream Hubitat MCP Server, CPU-core configuration, data retention, model responses, device state, home automation permissions or V1. The new view presents only the recorder's existing derived value.

**Acceptance:** after installing `2.0.0-alpha.16`, choose Hub Diagnostics → Detailed metric history → Native 5m load equivalent (%). Verify Y-axis and cursor show `%`, statistics show the corresponding percentage equivalents, and caption explains it is core-normalised **load**, not measured CPU utilisation. Switching to the separately available raw mode shows `load` units and original values from the same five-minute source timestamps. Real gaps must remain blank and no additional hub requests should be made solely to change the graph selection.

## First-answer quality instrumentation (original development roadmap)

After the alpha.16 diagnostics sprint, v2's next priority is model-led **source selection, historical coverage and correct causal confidence**, not further UI patches or hardcoded incident recipes. The clean v2 runtime and native flat tools remain unchanged in this evaluation milestone.

Use the private offline scorecard script:

    python hubitat-mcp-ai-v2/tools/first_answer_audit.py /private/path/technical.json --output /private/path/audit.json

It reads a browser-exported v2 Technical JSON, performs **no network/model/hub calls**, and reports observed tool/latency/source-coverage counts without disclosing private questions, answers, IDs, tool arguments, raw values, failures or event timestamps. It **never assigns an automatic factual accuracy score**. A human evidence review remains necessary, and inferred source completeness is not permitted. See docs/HUBITAT-MCP-AI-V2-FIRST-ANSWER-QUALITY.md for the frozen six-case read-only live matrix and first-answer assessment protocol.

The offline evaluator (audit schema v5) counts **bounded native log receipts** separately from device event history: actual returned rows, sources reporting more matches than returned, and reached request limits. A limited returned page cannot verify an absence of older errors, and source completeness always remains **not established**.

For direct device-control evaluation it also produces **`action_receipts`**, distinguishing: native device-command attempts vs echoed acknowledgments; embedded (possibly stale) state snapshots vs **later successful independent same-device attribute reads**; and, for generic `on`, `off`, `setLevel` commands only, whether the last returned requested attribute matches or differs. Nonmatching/unknown command types remain incomparable. **These are structural observations, not proof of physical actuation, causality or a correct AI answer.** The audit never reports private device IDs, raw values, arguments, source messages, timestamps, specific commands or personal questions. Synthetic tests cover flat/gateway results, failed/non-executed calls, stale snapshots, read-before-result confusion, different device IDs and privacy.

No add-on bump is needed to run this *evaluation-only* code, and no change to Hubitat devices, server permissions, model prompts, V1 or the external recorder is involved.

## Alpha.18 — visible and accessible clipboard feedback (8 November 2026)

The original **Copy answer** action copied the exact raw answer but left the button unchanged; the only acknowledgment was below a potentially long response. Alpha.18 adds a short-lived, high-contrast **✓ Copied!** success label directly on the clicked button and a live status beside the Answer heading. It also applies to **Copy technical details**, and shows **Copy failed** plus manual-copy guidance when neither the native clipboard API nor trusted-LAN fallback succeeds. Buttons and status reset after the confirmation interval, on a new question or when starting a new conversation; a late clipboard promise cannot restore a stale copied message on another request.

- The clipboard operation is awaited before any success feedback appears. Success never implies the clipboard call succeeded when it did not.
- Existing secure-context Clipboard API and LAN HTTP textarea/`execCommand` fallback remain available.
- Exact original answer text and downloaded/copied Technical JSON remain intact. No answer rewriting, extra model call, new native MCP tool, provider/auth, incident recording or Hubitat interaction.
- Automated synthetic JavaScript tests cover success labels, CSS state, live region, fallback, failure, expiry, old-request race and unchanged technical receipt content; repository browser/container tests remain required. **Installed visual acceptance pending**.
- To roll back, reinstall alpha.17. The generic source-gap annotation remains present in alpha.18; the reasoning-quality baseline is unchanged, with independent reviews documented in the First-Answer Quality Plan.

## Offline fixed-source A/B benchmark (no add-on update)

For a controlled, private comparison of the SAME source receipts with and without generic source-role notes, see docs/HUBITAT-MCP-AI-V2-FIXED-SOURCE-BENCHMARK.md and hubitat-mcp-ai-v2/tools/fixed_source_benchmark.py.

- The prepare command creates source-identical A/B pairs, a hidden balanced condition map and a blinded rating template, using *previously exported* Technical JSON. Exports containing prior source context are excluded from the self-contained sample. The original model answer is not shown in the paired prompts.
- Run each A/B prompt through the same model with NO live tools and separately preserve its unedited answer/latency. A human source reviewer grades grounding, source completeness, causal calibration, outcome verification and usefulness before unblinding. The report command verifies pair integrity and returns only aggregate, descriptive differences, not an automated correctness score.
- The generated folder contains raw private home/device information; keep it OUTSIDE GitHub and away from CI and public sharing. The code performs no model, MCP, network or device calls and refuses to create data underneath the repository.
- The installed add-on stays at **2.0.0-alpha.18**. This experiment does not implement new runtime answer rewriting, forced command verification, automatic retries or app-specific patches. Any future runtime changes require independent multi-domain evidence and their own tests.

## Optional private Ollama A/B runner

The offline fixed-source benchmark now has a separate, **explicit opt-in**
runner at hubitat-mcp-ai-v2/tools/run_fixed_source_pairs_ollama.py.
It can take previously frozen source-identical A/B inputs and ask the same
chosen Ollama model (e.g. the installed gemma4:31b-cloud) in independent
no-tools conversations, preserving unedited answers/timings for later
independent human blind review. **Dry-run is the default**. Explicit
--run and --acknowledge-private-mcp-data are mandatory, as is
--allow-cloud-model for cloud models (which may relay private household
source data from local Ollama to its provider). The runner is loopback-only
unless separately authorised, rejects remote HTTP, and never invokes
Hubitat/MCP or grades its own results. The default pilot is two paired
cases; complete ten-case evaluation is an explicit opt-in.

See docs/HUBITAT-MCP-AI-V2-FIXED-SOURCE-BENCHMARK.md for private Windows
setup and exact dry-run, model-run and human scoring steps.

## Alpha.19 — Hub Diagnostics full-page graph views (9 November 2026)

Both existing **Unified incident timeline** and **Detailed metric history** graphs now have a **Pop out full page** link in Hub Diagnostics. Each opens a new tab on the same HomeBrainOS origin, with a focused, full-width/height graph view and a **Dashboard** return link. This is a larger plotting surface, not a new graph data source or an exported image.

- Preserve the requested range, observed-data/full-window time axis, split/combined timeline layout, metric selection and (for the unified timeline) selected timestamp in the new tab; the selected time and display options are the **only** information placed in the URL. No chart samples, tokens or credentials are stored in URLs or browser storage.
- Both windows use existing read-only external-recorder JSON endpoints, interval markers, source distinction, keyboard navigation, pointer cursors and evidence readouts. Pop-out refresh fetches the same saved observations and never invokes Hubitat or the AI model.
- The full-page SVG recalculates its viewBox and plot geometry for screen size; the detailed graph canvas uses increased height and device-pixel scaling. On narrow screens the full-page timeline scrolls horizontally rather than shrinking labels to illegibility.
- Date-bearing timeline X-axis labels now have appropriate spacing **in logical SVG coordinates**, avoiding the overlap near midnight previously caused by using CSS width to count labels in a fixed-width SVG. The detailed chart's X-axis tick count similarly accounts for date+time label width.
- Browser regression tests exercise real pop-out tabs, large graph dimensions, no overlapping date labels, keyboard selection, retained metric selection and return navigation; unit tests cover safe URL construction and time labels.

**Scope:** UI-only version `2.0.0-alpha.19`. No model/tool prompts, command path, native MCP server, Hubitat devices, Home Assistant, recorder schema, backup/permission, V1 or underlying measurements change. **Rollback:** reinstall alpha.18, or revert the isolated UI/config/test/docs commit.

## Alpha.20 — drag-to-zoom in Hub Diagnostics (9 November 2026)

The Unified incident timeline **and** Detailed metric history now allow a selected-time zoom, including in their **Pop out full page** tabs. Drag horizontally across either plot with a mouse or pointer to shade a time interval; releasing zooms into that bounded portion of the existing observations. Drag again to zoom further, or select **Reset zoom** to restore the complete requested view. A short click remains source-time inspection; arrow keys still inspect the nearest saved observations, and Escape cancels a selection in progress.

Both plots use the **same zoom window** within a page, keeping synchronized memory/CPU comparisons aligned. Pop-out links carry the selected numeric time bounds together with the existing display-only range/layout/metric options. Selecting a new **Range** or **Time axis** option resets the manual zoom; switching split/combined or metric preserves it. No raw source rows, tokens or network identifiers are placed in the URL. The zoom overlay is only visual. It does not interpolate, generate extra samples, refetch history, or query the hub, and the saved source/gap/causality distinctions remain unchanged. For long-range records already downsampled by the recorder API, zooming displays **only the retained fetched data**, not hidden high-resolution points.

Browser and synthetic tests cover drag-selection overlay, zoomed interval, repeat zoom, reset, preserving single-click inspections and source-read-only boundaries on both full-page charts. The add-on UI, API and package version are all `2.0.0-alpha.20`. Existing v2 AI model/tool reasoning, Hubitat commands, HA, recorder storage, MCP server, backup/permissions, and V1 are unchanged. Updating the installed add-on is the user's separate action; rollback by reinstalling alpha.19.

## Alpha.21 — Phone-accessible private AI Benchmark page

The standalone v2 interface now has an **AI Benchmark** tab. Import the
previously prepared private A/B ZIP directly from a phone or tablet in Home
Assistant ingress. The page verifies frozen evidence hashes and stores original
source receipts, model answers and blind ratings under
`/data/homebrain-v2-benchmark/`, inaccessible to the live chat history.
Choose one or two cases per run, explicitly acknowledge private evidence and
cloud/remote model transfer, then use the configured model to generate
stateless **no-tools** A/B answers (temperature 0, seed 42). Model activity
can be stopped; completed results persist through add-on restart.

Review A and B alongside the unannotated original MCP source, score five
evidence-quality dimensions (0/1/2/n/a), and download an **aggregate-only**
comparison report. The interface never displays the hidden A/B assignment,
auto-grades answers, claims physical device causality or issues a native MCP
tool call. You can explicitly delete all locally stored benchmark material.
A cloud model such as `gemma4:31b-cloud` requires configured API access,
and submitting private evidence may incur cloud charges. No run occurs on
import, page opening or schedule. The download is an aggregate statistical
summary, never private questions/answers/sources or tokens.

The native v2 model-led loop, home device controls, Hub Diagnostics, external
recorder, HA, native MCP server and V1 are unchanged. See
`docs/HUBITAT-MCP-AI-V2-BENCHMARK-UI.md` for the full phone workflow and
privacy/rollback notes. Update to **2.0.0-alpha.21** to use this new UI.


## Alpha.22 — Autonomous First-Answer Lab (synthetic, model-led)

The fourth HomeBrainOS v2 UI tab evaluates native-model-selected MCP tool
discovery, evidence reads and initial answer quality on **six fresh fictional
cases** without connecting to your real Hubitat, Home Assistant, devices or
private A/B benchmark ZIP. The production \`Agent.answer\` loop operates
against an in-memory \`SyntheticMCP\` adapter; even allowed synthetic device
commands cannot reach real hardware. Each case is opt-in and capped at eight
model rounds and 24 synthetic calls.

The tab displays actual model/tool receipts, a source-retrieval coverage
checklist, a five-category **manual** answer assessment, and a source-free
JSON report. Cloud/remote model use requires explicit consent and may use
credits. No model requests or synthetic commands occur merely by opening the
tab. The original AI Benchmark page, native Ask/Chat and Hub Diagnostics
remain unchanged. Instructions and privacy boundaries:
\`docs/HUBITAT-MCP-AI-V2-AUTONOMOUS-LAB.md\`.


## Alpha.23 — Corrected native-contract synthetic evaluation

Following the first installed alpha.22 synthetic Lab 01 attempt, which
reached the model-round limit without executing the simulated command,
the evaluator now models the actual MCP gateway and device-command
wire contract rather than an invented \`params\` format. Leaf schemas
are disclosed progressively, as in the live MCP client, and rejected
calls report machine-readable safe diagnostic codes.

Failures are shown as **failed**, not answered. You can explicitly retry
a failed case without deleting all other synthetic results; the original
failed evidence is archived. The evaluation-only budgets are 12 model
rounds, 40 synthetic tool attempts and 120 seconds. All native MCP,
Home Assistant, Hub Diagnostics and v1 behaviour remain unchanged.
See \`docs/HUBITAT-MCP-AI-V2-AUTONOMOUS-LAB.md\`.

 
## Alpha.24 — Join downsampled diagnostic traces without masking outages

Hub Diagnostics' unified incident timeline and per-metric memory / CPU graphs
now join consecutive displayed samples **only when the saved recorder marks
them as belonging to the same continuous source segment**. Long views retain
first/last/min/max probe observations, so reduced point density no longer
appears as hundreds of disconnected short strokes. A changed `diag_segment`
still breaks the line. Raw and legacy unlabelled sources retain their cadence
gap checks, so unrecorded intervals are not presented as measured values.

This is a **chart-only/read-only** update. No recorder history, SQL storage,
probe schedule, native CPU calculation, causal attribution, Hubitat operation,
MCP write permission or synthetic evaluation changes. UI tests cover both SVG
incident timelines and canvas detail views, including segment boundaries.
Update the v2 add-on to **2.0.0-alpha.24** and reopen or refresh Hub Diagnostics.


## Alpha.25 — Reasoning A/B holdout (synthetic, isolated)

A new mobile **Reasoning A/B** tab tests whether generic evidence-quality
guidance improves the *current* Gemma model's first answer. Each of six new
fictional questions is run twice through the unchanged production
\`Agent.answer\` and fresh in-memory MCP fixtures. Candidate and baseline
differ only in an additional experiment-only general system instruction.
A/B labels are random and remain hidden until all six pairs are scored.

One pair at a time, with cloud/model consent. Source/tool receipts,
client-side validation errors, simulator rejections and a five-axis
blind human-scoring form are shown for each answer. Partial runs are
resumable; existing successful answers and private benchmark datasets
cannot be silently overwritten. The final report exports anonymised
coverage and scores, unmasking the candidate only after all ratings.
No real device is connected or controlled. No production agent
reasoning was changed.

The original Autonomous Lab dashboard now separately counts client-side
schema errors and simulator rejections. See
\`docs/HUBITAT-MCP-AI-V2-REASONING-HOLDOUT.md\`.


## Alpha.26 — immutable blinded reasoning ratings (9 November 2026)

The existing six-case Reasoning A/B holdout is unchanged; model calls, fixture
sources, candidate guidance, blinding assignment and native MCP behavior are
unchanged. A scoring-integrity correction now **locks each pair's A/B ratings
when saved**. Previously, the backend silently accepted a second score submission
even after the final six-pair report unmasked the labels, allowing
post-unblinding changes to the claimed blind results. The API now rejects an
attempt to replace a saved score, and the UI displays the saved values as
disabled controls. There is no implicit rating reset or hidden re-run.

Review both arm answers and source receipts carefully before clicking Save;
to start a wholly fresh study, use the existing explicit **Delete A/B results
and ratings** control, which also removes that study's synthetic results.
This release changes no production reasoning, diagnostics, credentials,
Hubitat or Home Assistant device state. The prospective six-pair Gemma trial
and post-install acceptance remain outstanding.
