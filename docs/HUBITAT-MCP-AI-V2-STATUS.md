# Hubitat MCP AI v2 — architecture and live acceptance

Updated: 2026-11-08
Version: `2.0.0-alpha.11` (candidate pending final-head PR/CI verification)
Development branch: `feat/v2-live-gateway-contract-alpha11`

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
