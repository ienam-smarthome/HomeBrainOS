# Hubitat MCP AI v2 — architecture and live acceptance

Updated: 2026-11-08
Version: `2.0.0-alpha.16` (merged release #1541, main 8a48743b136a49a8b915f140e3acad77c974cb90)
Development checkpoint: PR #1542 merged as `4e486befbc2cd996b6c9eaf635229efee94a0351` (evaluation only; runtime remains alpha.16).

## Current user direction

V2 is a clean, model-led client for the upstream Hubitat MCP server's intended capabilities: investigation, device control, automation authoring and administration according to the connected server/token permissions. Do not reintroduce v1 planners, incident-specific fixes, answer rewriting, fixed round quotas or a HomeBrain-maintained tool inventory. V1 remains separate.

This supersedes the earlier read-only-pilot architecture and alpha.2 frozen allowlist. A read-only token is appropriate for acceptance testing, but is a server permission choice rather than v2's permanent capability boundary.

## Architecture

Home Assistant ingress UI → standalone v2 API → Ollama-compatible model/function-call loop → Streamable HTTP MCP client → connected Hubitat MCP server.

The live server catalog is refreshed and paginated per request. Gateways accept empty calls for schema discovery and `tool`/`args` calls for execution; flat catalogs are supported. No fixed tool names or gateway-membership maps are enforced by HomeBrain. Unadvertised top-level tool names are refused; the server resolves gateway leaves and applies its own access checks. Tool calls are sequential and not automatically retried after an uncertain outcome.

The bundled upstream `SKILL.md`, `safety-guide.md` and `rule-patterns.md` are unmodified, pinned to upstream `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0` and include the MIT license. All three are supplied to the model. Live schemas and `hub_get_tool_guide` are authoritative. New automations should prefer native Rule Machine/Visual Rules; the bundled rule patterns describe legacy custom rules.

Calls carrying `confirm=true` pause for an explicit UI decision tied to one pending call and request. Approval is not inferred from assistant output or tool content, does not persist for another action and does not bypass hub backup or permission checks. Ordinary requested operations follow upstream identity and access guidance. No real device, rule, hub setting or permission is changed during repository development.

Credential redaction, per-call operational timeouts, the request deadline and explicit context truncation remain. These are resource/privacy safeguards, not answer-quality patches. The model owns the investigation and final prose.

## Evidence and recorder

Receipts contain the bounded, redacted source response shown to the model, with arguments, status and timing. Completed receipts survive later model failures. Receipts are browser-session responses, not durable archives or automatic follow-up context.

The external recorder source is unchanged from v1 and writes v2's independent SQLite file. No automatic v1 migration. Its UI/API read that database; the model's MCP loop does not automatically ingest recorder history.

## Verification history

- PR #1524 introduced the isolated alpha.1, merged as `fd02765b2e4ffa328445e3b41abb9ce147e87749`. The full check-runs endpoint verifies nine successful checks on development head `2f390e65efa4fb1312c903118bafde9545101769`. The v2 PR test log checked out synthetic merge `8215d43bc3635c08a00c381b02b5eddf50c1851e` and ran 10 tests.
- PR #1525 introduced alpha.2 receipts and a frozen read allowlist, merged as `9e2f345c076aed9f3c271faa1794457b8ca7ab8e`. Eight checks passed on its final head; 11 v2 tests. The allowlist diverged from the now-clarified upstream scope and is removed in alpha.3; receipt improvements remain.
- Alpha.3 CI/merge evidence is recorded on [PR #1526](https://github.com/ienam-smarthome/HomeBrainOS/pull/1526). Review the final head and actual workflow checkout before claiming validation. CI includes protocol/confirmation regressions, JavaScript syntax and amd64 Docker import/HTTP startup. It uses no live hub/model credentials.

## Installed alpha.3 interface mismatch

User-supplied logs confirm installed amd64 alpha.3 started and served status, but Ask returned HTTP 403 before model/MCP execution. The screenshot retained alpha.2's "read-only pilot" UI, and the log shows no new GET / after the alpha.3 restart. This supports an older open/cached page submitting without alpha.3's required request header; no live reasoning result was obtained.

Alpha.4 adds no-store response headers, bypasses cache on API fetches, displays the interface/backend version and checks that they match before Ask. A mismatch offers a cache-busting reload preserving the ingress path. Missing-header refusals explain how to reload. The request-header/confirmation safeguards remain enforced; no model or MCP behavior change. Close/reopen and refresh any already-open old page once after updating. Fix CI/merge evidence is recorded on [PR #1527](https://github.com/ienam-smarthome/HomeBrainOS/pull/1527); live recovery remains pending.

## Alpha.5 live tool-contract and schema-preservation fix

The supplied installed trace made seven calls with a gateway selector nested inside `args`. Every result was a schema catalog; no inventory/history query executed. The model's claim that devices could not be found was unsupported. Regex redaction also corrupted the embedded catalog JSON at `include_token`. This is failed live first-answer acceptance, not an empty hub or successful investigation.

[PR #1528](https://github.com/ienam-smarthome/HomeBrainOS/pull/1528) first adds synthetic tests on pre-fix commit `62b54ac1fcff2dc62168d3fdbad241327a523579`. CI reproduces all seven malformed shapes reaching the server, scripted discovery failure, JSONDecodeError and erased schema property definitions. No private household source is committed.

Alpha.5 validates arguments against raw live schemas using an offline reference registry. Gateway shape comes from schema properties, with no tool-name inventory. Payloads that omit a top-level selector while supplying nonempty nested arguments are rejected locally with the correct upstream call convention; the model can repair its next call. No silent argument rewriting or automatic tool retries. Empty discovery, tool-only invocation and valid flat/gateway calls are retained.

JSON-bearing text is parsed before credential redaction. Schema names/types/required fields/enums and JSON structure are preserved; actual credential values and defaults/examples are removed. Unchanged JSON source retains original formatting. Schema discovery is explicitly labeled as such in model context and receipts, with `operation_executed=false`; the original source is retained. No answer rewriting, fixed investigation sequence, upstream skill edit, heating-specific logic, v1 change, recorder change or permission bypass.

Final correction CI/merge evidence is tracked on PR #1528. Scripted recovery through discovery, inventory and history verifies the lifecycle, not Gemma reasoning. Real-model first-answer uplift and matched Thaura/Claude comparison remain unmeasured. Next: install alpha.5 and preserve fresh first-answer receipts without coaching or retries.

## Next acceptance

1. Install/update v2 alongside v1; verify ingress and real model/MCP connectivity. Other advertised architectures require deployment acceptance beyond the amd64 smoke.
2. Use an upstream read-only client token for first-answer investigation comparisons. Ask the same frozen question with no prompt repair and preserve answers/receipts.
3. Compare lighting, humidity, heating and hub-incident questions against matched v1/Claude/Thaura evidence. Publish sample counts, provider/model, code version, latency, missing sources and unsupported claims; do not claim quality from unit tests.
4. Test device control and native automation only with explicit user-authorized test operations and upstream safety requirements.

Live first-answer usefulness, factual grounding, model comparison, control/automation behavior and Home Assistant installation remain **not measured/unverified**. No unattended development is implied.

## Alpha.6 UI conveniences and current evaluation direction

User requested separate answer/technical-detail copying and visible response time. Alpha.6 retains the original API response in copied technical details, alongside question, model, request ID, browser elapsed time and server elapsed time where available. LAN HTTP clipboard fallback and failed-request copying are covered by isolated UI tests. Model, prompts, schemas, MCP access, recorder and answer generation are unchanged. No live model or hub calls are used for this UI validation.

Current evaluation direction: assess existing Ollama Cloud Gemma4:31b with varied read-only first-answer questions; preserve all failures and raw receipts before deciding any changes. Do not resume model routing experiments, heating-specific fixes, coaching or answer rewriting. This UI release makes evidence easier to capture; it is not evidence of reasoning improvement.

## Alpha.7 daily-use interface and evaluation direction

User authorized v2 usability development and continued comparison with v1 before choosing a daily assistant. Alpha.7 adds safe DOM-only Markdown/table/code rendering, original-text access, page-session conversation history and reset, evidence JSON download, responsive spacing/focus styles and a visible recorder-disabled explanation. It also corrects the diagnostics tab ID mismatch. Copy operations preserve original answer text; no raw HTML is interpreted. No transcripts are persisted by this UI.

Model prompts, upstream skills, agent/MCP code, permissions, recorder source and v1 remain unchanged. Follow-up context remains prior prose only, not prior tool receipts; the UI explains this. Formatting is not answer rewriting or proof of factual accuracy. Confirmation controls remain attached to backend operations.

Local UI regressions cover formatting/XSS, raw copies, downloads, session reset/history, busy-state reset refusal, timing/errors, diagnostics empty state and tab target. CI includes Python runtime and Docker startup. Installed desktop/mobile acceptance and day-to-day usefulness remain pending.

Recent evaluation: Gemma can summarize richer frozen G06 evidence but previously looped on tool selection; Beam also made unsupported claims. Production-code replay is byte-verified. Fresh investigation comparisons remain limited by captured-query coverage; the latest expanded attempt timed out before either first model response. Do not infer a model winner, train case-specific skill rules, or replace the default model based on those runs. Private fixtures/tokens remain outside the repository.

## Alpha.8 — evidence-aware session follow-ups (8 November 2026)

The user approved the next evaluation milestone and correction of the alpha.7 follow-up limitation, while asking to retain existing upstream MCP write permissions and confirmation behavior unless a serious risk is shown. The alpha.7 UI sent only prior prose; source receipts did not survive into model input on subsequent questions. Alpha.8 introduces a small server-origin, redacted, **memory-only** receipt cache keyed to the open browser conversation. Prior source excerpts include tool identifiers, arguments, capture time, success, bounded result text and truncation markers. The client does not submit source receipts; only the agent's actual tool responses are retained. Old values are historical and cannot authorise new device writes or substitute for a necessary fresh check. The model remains responsible for interpreting them and selecting further tools. New conversation rotates the ID and erases server-held evidence, and expiry/eviction bound memory.

The upstream skill files remain unchanged. V1, recorder source, provider routing, server permissions, `confirm=true` approval, and tool selection are unchanged. No deterministic causal fixes, automatic retries or per-incident logic were added. A server-side cache gives stronger receipt provenance than trusting arbitrary browser-provided observations; the UUID remains a session capability, so preserve normal Home Assistant ingress and keep the direct port disabled.

**Evidence gate:** Browser/HTTP/Python regression tests verify the data flow, truncation, masking, reset, expiry and isolation using synthetic MCP/model responses. The private G06 first-answer capture and Ollama Cloud credentials are not part of the repository. No live Hubitat/Gemma replay or matched Claude/Thaura evaluation is asserted. The next installed acceptance uses the frozen cross-domain matrix in `docs/HUBITAT-MCP-AI-V2-ACCEPTANCE.md` and exported first-answer technical JSON, including at least one dependent follow-up per domain. Previous timeouts are failures, not a successful comparison.

CI and PR exact-head verification: **pending until the final candidate passes.** No unattended work runs after this session.

## Alpha.9 — real follow-up source loss and generic readback milestone (8 Nov 2026)

The user provided three installed alpha.8 technical JSON exports from a read-only cross-device heating question and two follow-ups. The first answer had **10 tool attempts, 2 local contract rejections, 8 successful reads**, including the main controller's 58 returned events and five radiator histories. The first answer incorrectly reported a most-recent interval and extrapolated later snapshot values backwards. Each follow-up was fast but used **five prior snippets and zero new MCP tools**, falsely asserting that original main controller history did not exist. The complete original receipt was present in the first technical export but absent from the alpha.8 follow-up excerpt budget. Individual device event histories were bounded (some showed 100 recent events), so absent older events in those pages were **not** evidence of historical absence. Do not commit private device history or real model outputs to the public repo.

Root cause addressed: alpha.8 kept short latest-first source excerpts without an index of *all* prior reads. Alpha.9 adds compact provenance and returned event-time span metadata for every retained source plus a server-side capped archive of each redacted original source string. A single read-only client-owned model tool retrieves older source chunks on demand by opaque receipt ID. The model can also rerun a correctly scoped native MCP read if the old archive is incomplete. It is **not** an automatic replay mechanism, local causal verifier or expanded write capability. This general mechanism applies to lighting, humidity, heating and hub-incident histories alike.

Operational protections: one session UUID, source IDs scoped within it, memory-only, bounded index and bytes, explicit truncation/eviction signals, no new Hubitat writes, existing upstream confirmation/permission boundaries unchanged. Preserve `New conversation` reset and 45-minute idle expiry.

**Acceptance:** scripted test sources must reproduce an earlier important record followed by several large newer sources, verify the earlier source appears in the index even when excerpt truncated, prove the model can request the original in chunks without contacting Hubitat, and fail closed for wrong/expired IDs. Live alpha.9 result still requires a first uncoached answer and dependent follow-up; do not claim corrected Gemma reasoning merely from tests.

PR, exact-head CI, final status and merged SHA: **pending verification**.

## Alpha.10 — cause vs hypothesis evidence standards (8 Nov 2026)

A real alpha.9 heating-history follow-up correctly found only 11 filtered events per TRV, then asserted a Hubitat event-retention ceiling was the **most likely** explanation and claimed no further MCP query could recover the records. The answer ran in one model round, with 13 prior indexed sources, 11 snippets and **zero** new read calls or local prior-evidence retrievals. It did not compare native Event page records, inspect alternative return-source coverage, or independently verify purging. **Cause remains unverified.** This error generalizes beyond heating: a limited observational result does not distinguish retention, limited endpoint result, reporting gaps or query behavior.

Independent review of the upstream MCP v5.1.7 Groovy implementation shows `_fetchBypassDeviceEvents` uses `hubInternalGet("/device/eventsJson/${deviceId}")` and `_deviceHistoryBypass` applies attribute/date/limit filters to that returned array. This does not establish the endpoint's depth or native store retention. References: `kingpanther13/Hubitat-local-MCP-server` `libraries/mcp-devices-lib.groovy` around lines 692–710 and 3151–3194. **Do not claim native-hub purge without independent comparison.**

Implement a **general** client-side `client_event_source_scope` annotation, preserving the original model-visible MCP `content`, with returned count, returned event timestamps, requested time/limit scope and explicit unknown completeness/causality. Add short model-led evidence discrimination guidance to the v2 prompt, not incident-specific instructions, vetoes, mandatory extra rounds, answer rewriting or a new causal planner. The evidence annotations are derived from the same returned rows; they do not independently certify a cause. Real alpha.10 first-answer reasoning and native Hubitat Events-page cross-check remain unverified.

Scope: `hubitat-mcp-ai-v2` and v2 development notes only. Existing user-approved upstream write/confirmation behavior remains untouched. The native Hubitat Events-page comparison needs authorised local inspection; repository development alone cannot see the hub. The private exported technical JSON does not belong in Git history.

PR merge SHA/CI: pending exact-head all-green check before merging.

## Alpha.11 — unambiguous model-facing live gateway schema (8 November 2026)

The installed alpha.10 Gemma4 cloud reboot investigation supplied by the user returned a well-supported firmware-update/startup sequence but required **six** model rounds and **five** MCP attempts, of which only **two** succeeded. Three attempts used malformed gateway arguments (selector nested under `args`, then repeated as leaf `args.tool`, including a similar diagnostic gateway error). These were model-generated protocol mistakes, not hub failures. Exact private technical JSON remains outside GitHub.

Enhance the **presentation** of any server-advertised gateway-shaped `inputSchema` (detected by *both* `properties.tool` and `properties.args`, no name lists or hard-coded leaf schemas). Use a deep copy for model-visible descriptions and top-level `additionalProperties: false` matching existing server gateway enforcement; retain the live enum, leaf selection authority, normal/flat tools, catalog discovery `{}`, original validation schema and upstream skill verbatim. The model continues selecting the gateway and leaf. A non-gateway tool with an `args` object containing an ordinary `tool` data key must not be affected.

Additionally reject the duplicated leaf selector `args.tool` locally for gateway-shaped schemas before any `tools/call` request; never guess, reparent, autocorrect or retry. Preserve existing permission and approval contract: writes are still upstream-authorized and confirmed only per current rules; no write is executed by this release itself.

Synthetic regression tests cover live enum retention, model-facing call shape, original catalog immutability, unrelated direct tools, no-network duplicated-selector rejection, unchanged good-call payloads, discovery and a scripted first model call. The scripted model is **not** a real Gemma evaluation. Native source scope sidecars, alpha.9 prior-evidence archive, external Hub Diagnostics recorder and v1 remain untouched.

Post-merge installed alpha.11 quality acceptance **pending**: exact version, uncoached read-only first attempts in unrelated domains, complete technical JSON, malformed-call rate, model rounds and answer support. Avoid promising error-free Gemma behavior until observed. PR/merged SHA and CI to verify.

## Alpha.12 — discover selected leaf contracts from upstream (8 Nov 2026)

The latest installed alpha.11 first-answer reboot analysis answered the firmware-update question with defensible source records and no selector-placement errors, but incorrectly used `hub_get_logs(mode=hubEvents,sortBy=desc)` and spent 5.24 seconds on an unrelated `past` log dump. The upstream v5.1.7 `hub_get_logs` **leaf** inputSchema, found in `libraries/mcp-diagnostics-lib.groovy`, describes `sortBy` as applicable to `devices` and `apps` modes. The top-level `tools/list` gateway schema cannot express every leaf's field-specific restriction. No hardcoded remedy for `hub_get_logs` or individual modes is appropriate.

Model-selected, generic implementation: after a selected gateway leaf is proposed, fetch that gateway's `{}` metadata-only catalog once per unchanged connected catalog, cache the available `inputSchema` and descriptions, and check only structurally declared JSON Schema constraints. Return local, nonexecuted `contract_error` for invalid typed arguments. Include the selected leaf schema/description in the model's **next** tool definition and later requests. The client does not extract hardcoded natural-language restrictions into invented validation rules. A prose-only restriction can still yield an upstream error on first use; this limitation must be visible, not masked. No hidden mutation, automatic retry, source-query replay, new authorizations or fixed model rounds.

Operational scope: read-only schema fetches are additional MCP metadata requests, tracked in `leaf_schema_discoveries`, not device reads. Cached selections invalidated if live tools/list changes. Optional metadata failure must not prevent a previously valid native tool call or gate writes differently. All user-owned device/tool permissions, `confirm=true` approval, upstream skills, v1 and external recorder unchanged. Model remains responsible for search and stop decisions.

CI uses a synthetic MCP server exposing multiple leaf schemas and a stub model; tests verify one catalog probe per gateway, cache invalidation, field descriptions, local validation without a native side-effect, exact passthrough of valid requests and unchanged direct tools. Live installed Gemma performance **unverified**; compare real first-attempt technical JSON before recommending further changes.

PR head, exact CI results and merge SHA: pending verification.

## Native flat MCP vs gateway evaluation — no v2 runtime change (8 Nov 2026)

The user requested comparison before any further architecture change after alpha.12's live Gemma result: three malformed nested gateway selector attempts, one invalid `sortBy='desc'` leaf request (locally rejected), and four eventual successful reads in 13.78 s. Alpha.11 first-call gateway formatting had been better, so the observed difference may reflect model variability; one run cannot establish an alpha.12 regression rate. The separate claim about free-memory history must still be checked for appropriate incident-time coverage.

**Upstream code finding:** the native Hubitat MCP server already offers a genuine flat catalog via its existing `useGateways=false` (**Consolidate tools behind category gateways: OFF**) setting. In this mode the server advertises every visible leaf with its direct inputSchema on `tools/list`; it enforces the same Read/Write masters and advanced overrides, hides `hub_search_tools`, and explicitly refuses stale gateway-name calls. The setting is **server-wide**, affects other clients' catalog assumptions, and must be restored after an authorised test. V2 already accepts direct leaf calls and validates the live top-level schema. There is **no evidence justifying a new client-side proxy** or a version bump just to try native flat mode.

Added synthetic gateway-versus-flat compatibility regressions with identical mocked event results and test isolation of hidden writes, confirmation and catalog refresh. Real installed Gemma context size, model success, tool latency and hub-side flat-mode behavior are **unverified**. Only a controlled read-only A/B on the installed hub can decide; see `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md`. Do not change Hubitat settings, credentials or permissions from this repository work. The user must knowingly accept the global mode switch before it occurs.

Repository evaluation test PR/CI: pending.

## Three installed flat-mode runs — provisional choice (8 Nov 2026)

The user switched upstream MCP Server `Consolidate tools behind category gateways` OFF and supplied three complete first-answer Gemma4 cloud Technical JSON exports from unchanged v2 alpha.12. **Results:** G1 reboot 5.792s, 1/1 tool success, 2 rounds; G2 five recent device events 8.815s, 2/2 successes, 3 rounds; G3 OFF-cause investigation 11.962s, 5/6 successes, 7 rounds. Combined: **8/9 native tool attempts succeeded**, **one local type-schema rejection, zero nested gateway-selector failures**, and average **8.856s** wall time. All three answered the primary request; G3 independently retrieved the automation and two motion sensors. The configured 15-second inactive delay and the last motion-inactive event preceding the OFF command by 15.128s strongly support the proposed mechanism, but do not establish an independently logged timer callback or exclude all alternatives.

The matching alpha.12 gateway **G1** took 13.779s and 4 rounds, with 4/8 model attempts successful and one leaf catalog discovery. Flat mode G1 used 5.792s, 2 rounds, 1/1 success, no discovery. This is one measured paired improvement, not a reproducible performance distribution. G2 `prior_receipts_used=1` is not a perfect isolated first-turn comparison. No other mode-matched causal trial exists yet. Source-output confidence is still overcalibrated: the model sometimes asserts a cause is completely verified when temporal correlation/configuration only strongly supports it.

**Important safety uncertainty:** `do not change anything` and observed read-only operations do not verify *effective* token permissions; a separate earlier `hub_get_info` response reported `writeEnabled:true` but not all per-client grants. Verify Read allowed / Write denied on the actual test client without using a write as a probe. The server-wide flat-mode switch also affects other clients and may need rollback. No device settings, token permissions or MCP server settings were changed through this GitHub development update.

**Development decision:** Preserve the working alpha.12 runtime and model-selected direct tools, no v1-style causal planner, no new router or hardcoded input corrections. Native flat mode is the leading observed candidate only, not a universal default. Freeze F1 humidity and F2 multi-room heating first-answer questions for a broader evidence-timing and cross-domain test; see `docs/HUBITAT-MCP-AI-V2-FLAT-MODE-EVALUATION.md`. Only aggregate results may be committed. Live client access and other connected-client compatibility are not verified by GitHub.

## Alpha.13 — browser rendering and flat-mode heating-answer review (8 Nov 2026)

The user supplied a screenshot of a raw TeX escape rendering in an alpha.12 historical room-heating comparison, together with the complete first-answer Technical JSON from the installed flat-mode Gemma4 cloud model. The table showed literal `$21.0^\\circ\\text{C}$`, `$\\rightarrow$` and `$\\sim$`. The frontend's `renderAnswer`/`appendInline` implements a deliberately small Markdown subset with no math handling, so the defect was strictly **display**, not a bad MCP result or historical event corruption.

**Implementation:** Add a narrowly bounded, offline inline-TeX-to-safe-text display layer for common symbols (`°C`, arrows, inequalities, approximations, Greek symbols, numeric exponents/indices). Preserve Markdown code literals, original API answer text, raw-view/copy/export, all event receipts, and any unsupported TeX unchanged. No HTML parsing or external library/CDN, no math evaluation, no model-specific output instructions or cause-specific fixes. Tests cover UI VM and Chromium desktop/mobile as well as XSS and exact technical JSON preservation. Bump UI/service/add-on to **alpha.13** so ingress refreshes correctly. Complex formulas (e.g. fractions and matrices) are intentionally **not** typeset by this small renderer.

**Source-verified answer assessment:** Eight direct read-only MCP calls, **8 successful, 0 rejected**, 4 model rounds, 15.893s browser / 15.831s server, no prior receipts or schema discoveries. The main thermostat reported `heating` at 09:33:33 UTC, `idle` at 10:00:22; one bedroom TRV reported `heating` from 09:30:15 to `idle` at 10:00:03 and had actual device-reported heating-setpoint changes from 22 to 21 degrees. Four other TRVs returned no thermostat operating-state rows in their **requested 09:30–10:10 UTC** history excerpts, though some unrelated rows or setpoint **commands** were present. Thus the conclusion “not all TRVs were idle” is supported, while the other four states remain **unverified**, not demonstrably idle. Model table called commanded setpoints “Observed Setpoint Change” for these devices, which overstated evidence. It also said no main-thermostat setpoint change was recorded without querying that setpoint attribute. Correct future investigations should distinguish command receipt, confirmed physical state, and absences limited by returned source coverage; this is documented, **not** enforced with any new planner/claim patch.

Native flat mode remains the *observed leading interface* but not a proven universal default. A previous report of enabled write permission still requires client-specific verification before treating a natural-language read-only question as an enforced permission. No live Hubitat, HA, router or upstream server modifications in this repo release.

PR head, CI and merged SHA: pending final verification.

## Alpha.14 — native load line repair and source-scope guidance (8 Nov 2026)

The user's installed alpha.13 screenshot of **Hub Diagnostics → History → 24 hours → Native 5m load** showed many isolated dots during the hours with recorder samples. Code review found a definite local mismatch: the recorder's raw (short-history) `samples` array contained repeated 30-second polls holding one cached native five-minute observation, while only the first source-labeled row had a `diag_segment`. The canvas renderer tested successive rows for equal `diag_segment`, causing repeated cached rows to be rendered as tiny strokes. The graph is **not evidence that the hub had dozens of independent native measurements or outages**. No external recorder SQLite or real probe responses were available to independently verify specific timestamp/collection anomalies. Empty earlier portions of a 24-hour range can be explained by a recorder that began collecting later or by unavailable readings; do not invent historical data.

**Repair:** For native-only values, only return one source-labeled row per distinct native source label in raw chart history (long-window logic already deduplicated). Preserve raw poll count separately, all original OS-memory probes and failure segment detection, 15-minute true native gap boundaries, exact source/collector timestamps, and actual extrema. Add visible native-line connections and small markers, fractional Y tick precision, a caption showing observation/poll counts, and browser regression on desktop/mobile confirming two connected genuine segments but not across the true 20-minute gap. **The separate CPU-equivalent percent is derived from five-minute load / configured cores**, not a direct hardware utilisation metric.

Generic model-led answer quality: extend only the source-integrity skill guidance, requiring the model to compare any all/none/every group conclusion against actually checked members, attributes and time periods, to distinguish commands from confirmed device-state changes, and to qualify missing/empty bounded reads as unverified. No automated veto, rule-specific patch, fixed planner, artificial model rounds, device changes, permission updates or model routing are introduced.

Version `2.0.0-alpha.14` for backend, add-on and UI. Tests: native short history dedupe, native longer-history extrema, true outage/long-gap segmentation, unchanged externally sampled OS series, canvas line continuity and tick decimal labels in Chromium and existing UI/model safety tests. First real installed UI verification pending. PR head, checks and merge SHA pending.

## Alpha.15 — V1-quality independent timeline UX (8 Nov 2026)

User feedback after confirming alpha.14 native sampling graph repair: **V1 still has significantly more useful and functional graphs.** Their V1 screenshot illustrates source-aligned memory and CPU panels on separate scales, point cursor/time readout, a local incident/event summary, accessible detailed chart with statistics, and investigation buttons. V2's prior combined/detailed canvas was valid source data but less usable, especially over a 24-hour range when recorder history covered only six hours. Do not mistake the UI shortfall for a native Hubitat CPU telemetry defect.

Implement an **SVG unified timeline in v2**, using the existing external SQLite `/api/diagnostics/timeline` response. Default aligned split memory (external probes) and CPU load equivalent (native five-minute measurements), optional shared plot with independent axes. Include nice source-specific grid ticks, genuine source continuity and exact timestamp cursor, native label and source provenance, offsets/confirmed system starts, external outage bands and observed extrema in a bounded event list. Buttons inspect **only stored source records**; prepare an AI question in the Ask tab without executing tools or authorising a write. Open original same-origin JSON via normal link. No V1-only historical journal UI or automatic model invocation.

Also improve the existing V2 detailed metric graph with unit-labeled axes, min/max/latest stats, keyboard/touch point inspection, and the same time window controls. Choose 6h initial range and default to **fit data** to avoid showing a mostly blank 24h axis when only recent observations exist. Explicitly allow **full requested range** to show blank periods; no missing data is backfilled, nor is fit-mode a claim of earlier complete coverage. Preserve real data extrema, recorded gaps, causal qualifiers and recorder independence, and keep V1 entirely untouched.

Synthetic browser and JS regressions test UI behavior in both desktop/mobile widths, with no live Hubitat or model calls. Existing alpha.14 recorder dedup, MCP native flat mode, permissions, source-scope inference policy and complex-math display unchanged. Installed review pending.

## Alpha.16 — raw native load vs core-normalised percentage (8 Nov 2026)

The installed alpha.15 phone screenshot shows **Native 5m load** axis and tooltip expressed in load-average units (native value approximately 0.6). Although the V2 **Unified incident timeline** already charts native load-equivalent **%**, the *Detailed metric history* dropdown selected the unscaled `native_load5` field and therefore showed `0.6 load`. User requested that native load be presented as a percentage.

Source audit confirms `external_hub_diagnostics._with_load_pct()` already derives `native_load_pct = round(native_load5 / cpu_cores * 100, 1)`; it exposes `cpu_cores` in the history and status responses, and `native_load_pct` is a permitted history metric. No new recorder calculation, inferred core count, data persistence changes or Hubitat read needed. **The derived value is five-minute load-equivalent percent, not direct CPU utilisation**, and values over 100% remain legitimate demand indicators; do not clamp to 100%. The raw native load is preserved separately for expert inspection.

Only the detailed chart metric selector/legend/provenance/cursor and v2 version require changes. The main option now selects live `native_load_pct`, the raw `native_load5` remains a secondary option, and the caption reports configured source core count and normalization. The combined timeline and original historical readings are unchanged. Browser tests must inspect actual `%` labels and native source gap behavior at desktop/mobile sizes, plus raw-load reversibility and exact source-time alignment. Python regression verifies source raw values remain immutable and backend normalisation uses configured core count. No V1, MCP permission, model, hub or SQLite mutation.

PR/CI and installed acceptance: pending final check and first user screenshot.

## Return to original v2 agent-quality roadmap — first-answer measurement

The next milestone is **not another Hub Diagnostics feature**. The original v2 problem after native flat-tool improvements is **correct, source-complete model-led investigation on first attempt**. Repeated multi-TRV and motion-timer answers show source selection and output-claim confidence still need evidence-grounded evaluation. Five-minute load display is complete and separately verified via alpha.16.

New **purely offline** script in hubitat-mcp-ai-v2/tools/first_answer_audit.py accepts the browser's private Technical JSON. It outputs bounded *counts and evidence-observation limitations* without disclosing private answer text, request parameters, device identifiers or event records. It reports native calls versus metadata reads, rejected operations, prior evidence, source-reported event rows, sample-dependent latency, and **not_measured** quality fields. The importer does not access the model or hub and never grades truth from lexical text or successful MCP calls.

A new freeze-and-review protocol covers reboot, lighting cause, humidity duration, historical room-demand, FanBoost and offline/stale-telemetry cases; see docs/HUBITAT-MCP-AI-V2-FIRST-ANSWER-QUALITY.md. The earlier curated 40 source-only packets remain separate from live native MCP benchmarks; passing one is not evidence of the other.

**Next user action:** one fresh V2-R5 FanBoost read-only question, first answer + Technical JSON, with effective test client's Read allowed / Write denied verified through configuration (no write probe). Then assess source coverage and provenance before planning model-quality code. Do not interpret this tool/CI milestone as validated Gemma quality or a new alpha.17 runtime. PR #1542 merged as `4e486befbc2c`; the merge commit's Release assurance, v2 pilot, Answer quality scorecard integrity and Validate HomeBrain OS workflows completed successfully.

### 8 November V2-R5 first-answer review (no runtime change)

The user provided an actual private alpha.16 Gemma cloud Technical JSON for the frozen FanBoost question. A direct source review found 13/13 successful native calls across six model rounds, 18.480 seconds browser elapsed, and three event-history responses with 19 combined rows. A scheduled-cycle interpretation was **strongly supported**, but Gemma falsely declared the cause fully verified and claimed all configured humidity sensors were below threshold despite missing focal-time humidity coverage and not querying one configured sensor at all. App command issuance and physical reporter were recorded; the precise internal scheduler callback was not. Assessment: **PARTIAL** first answer, **causal certainty overclaim**, **incomplete monitored-sensor historical coverage**. No cross-domain quality denominator is yet available; no production reasoning code patch justified from one case.

The approved evaluation-only audit tooling must now recognise actual native `content[].text` event-row responses even when no `client_event_source_scope` annotation exists. This is separate from the previous successful-only scope filter and must not infer event uniqueness, upstream retention, complete windows, or cause. Preserve the private raw export outside GitHub. The next recommended frozen question is V2-R3 (historical humidity thresholds). No Hubitat/HA/recorder/MCP setting or runtime version changes.

### Evaluation-only audit integrity follow-up (candidate)

The offline Technical JSON importer must not inflate event-history coverage from a failed MCP call or a metadata-only schema/catalog receipt that happens to contain a scope-shaped JSON object. Limit counted event histories to successful native source responses, explicitly count discarded scope-shaped receipts, and preserve **unknown unique event count** across overlapping responses. Also avoid echoing externally supplied model/tool names or argument keys in supposedly private-safe aggregate exports; use a model fingerprint and structural counts instead. This is an evaluation-format v2 update **without runtime or add-on version change**. The live answer-quality baseline remains unmeasured pending the frozen FanBoost first answer.
