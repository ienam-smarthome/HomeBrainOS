# V2 alpha.64 — live MCP catalog inspection and scoped discovery failures

**Date:** 12 November 2026. **Scope:** V2 normal Ask native tool-discovery lifecycle; read-only metadata only. **Installed first-answer acceptance:** not yet performed.

## Source-real motivation

Three consecutive private first-answer reviews in a daily-use permission investigation showed contradictory unsupported verdicts. The latest alpha.63 receipt attempted `hub_search_tools` three times, with each request rejected locally because the *search helper itself* was not in the connected `tools/list` catalog; it then incorrectly reported that the *target* command was not exposed. The only successful read was a best-practice guide describing a class of write tools, not an active permission check. Neither global `writeEnabled=true` nor a document mapping a tool to a guide section proves a specific client's write authorization. Do not commit household IDs or private receipts.

## Root cause and design

V2 already reads the live paginated native `tools/list` catalog on each Ask, and only offers declared tool definitions. The model can still request a hallucinated or documentation-only tool name. A plain `Tool is not in the connected server catalog` error does not expose the useful actual catalog or distinguish unavailable *discovery method* from unavailable *target capability*. In gateway mode, a leaf may appear only inside a gateway selector's advertised `tool.enum`; in flat mode it may be directly listed while a search helper is absent.

Add one **read-only, model-selected local catalog inspector** to the existing agent, not a separate MCP server or search backend:

- `homebrain_inspect_mcp_catalog({})` returns the exact top-level names from the successful current-request `tools/list` snapshot.
- `homebrain_inspect_mcp_catalog({name})` returns the *direct* tool definition and schema only if actually listed. It also reports matching **gateway candidates** only when the server's actual gateway-shaped `inputSchema.properties.tool.enum` contains that exact leaf name; no guessed names, docs-to-gateway inference or arbitrary string matching.
- A gateway candidate is *not* a verified leaf schema. The model can choose to call the **advertised** gateway with `{}` to retrieve its server-origin leaf definitions without executing a device operation. Only original upstream responses determine the leaf schema.
- A model's call to an unavailable top-level tool is rejected before approval or any network dispatch with `result_kind=unavailable_tool`, `operation_executed=false`, and a scoped catalog-navigation receipt. That is proof **the requested name was absent from that request's top-level catalog**, not proof another tool/leaf or capability is absent.
- The local inspector never invokes MCP, refreshes the server, executes device commands or grants permissions. Tool exposure can establish metadata visibility; it cannot establish *effective write authorization* or execution success.
- Expose the inspector during the already restricted read-only source-review stage; retain the existing no-write restriction there. Original metadata and errors stay available in private Technical JSON.

No hard-coded device/tool command routing, prompt-keyword mutation classifier, automatic real tool retry, custom scheduler, Rule Machine creation, deterministic answer rewrite, source forgery, or additional model round.

## Synthetic acceptance

`test_catalog_inspection.py` checks:
1. A genuine flat catalog entry returns the exact advertised native schema; absence of `hub_search_tools` alone does not erase that entry.
2. A gateway-shaped catalog surfaces only the explicitly advertised leaf as a *candidate*, without inventing its full schema or proving client permissions.
3. Invalid inspector arguments fail closed; the inspector is available during read-only review.
4. A scripted model first requests an unavailable helper, then selects the local inspector and a gateway `{}` catalog read. The test asserts one real native **read-only schema discovery** and **zero native device writes**.

This regression demonstrates the *mechanism*, not that Gemma selects it on the first try, or that a particular command is authorized on an installed Hubitat instance.

## Deployment and next source-real test

Install alpha.64 only after required exact-PR-head validation and release workflows pass. Ask a fresh read-only question about an unrelated native capability's live exposure and exact schema without suggesting `hub_search_tools`. Inspect original Technical JSON for either `local_catalog_read`, live gateway `tool_catalog`, or a direct catalog schema; reject answers that treat an unavailable helper as absence of the target. Assess accurate distinction among global Write master, top-level tool visibility, gateway-leaf discovery, client permission and actual execution. Never perform a live write to test permission unless separately approved.

Preserve V1, Hub & Device Monitor, diagnostics, existing upstream Read/Write/token/confirmation gates and earlier evaluation tracks. **Outcome remains unverified until installed, model-led first-answer review.**
