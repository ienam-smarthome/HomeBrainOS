# Hubitat MCP AI v2 — architecture and live acceptance

Date: 2026-11-07
Version: `2.0.0-alpha.5`
Development branch: `feat/v2-upstream-native-mcp`

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
