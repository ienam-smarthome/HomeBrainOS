# HomeBrainOS v0.18.415 — fix global automation-status route stealing focused questions

## Installed v0.18.414 acceptance failure — 5 November 2026

The user submitted the prior read-only exact-ID retry prompt for existing native Rule Machine dated triggers **2967 and 3985**. The message explicitly asked for stored time/date field types and values, inventory verification, and `hub_set_rule(operation=read)` only. Its final sentence stated: "Keep native rule-writing authorisation disabled."

Instead, HomeBrainOS returned its generic **automation-status** dashboard after approximately **1.0s**, showing 166 automation items, 124 app instances and 42 Rule Machine entries (147 enabled/not-disabled, 18 disabled, one paused). The response highlighted paused rule **3985** ("Internet: Google TV block @1hr") but **did not inspect either exact rule ID for native date fields**. The dashboard's current inventory counts are not inherently false; they simply answer a different question. This test is a **request-routing false positive**, not evidence that 2967 or 3985 now have valid or missing saved date fields.

## Confirmed root cause

`app.py` selects `AutomationStatusService.matches_request()` before the unified/specialist agent. The prior matcher treated any occurrence of `list`, `show`, `which`, `status`, `active`, `disabled`, `paused` or `broken` together with any reference to `rules`, `automations` or `apps` as a broad inventory request, irrespective of user intent. The final restriction **"Keep native rule-writing authorisation disabled"** therefore made a focused source-only retry look like a global automation status query. A fast completed response here concealed that the intended read had never run.

## Narrow remediation — retain the genuinely useful feature

- Keep the deterministic global automation inventory/status renderer and its filterable Active, Disabled, Paused, Broken and Unknown groups for **explicit global list, status, count and advisory-idea requests**. Removing that entire UI would regress a legitimate use case.
- Do not use incidental `status`/`disabled`/`list` words as intent signals. Require **positive broad inventory/status phrasing** (e.g. `List every automation`, `Which rules are paused?`, `Automation status`, `How many rules are active?`). Named exact-ID reads, existing native dated-trigger investigations, and safety instructions are excluded.
- Protect `is_existing_dated_trigger_question()` in **both** the status matcher and the /api/ask shortcut selector. That read-only specialist path remains the owner of source-scoped exact-ID retries and can no longer be accidentally displaced by an incidental UI vocabulary match.
- Preserve normal broad queries and new automation-ideas access. No changes to native MCP document read/write operations, exact-ID membership safety, dated-rule authoring minimum version, confirmation/backup/duplicate gates, or existing device actions.

## Regression and installed acceptance

Tests replay the full failed user prompt, several near-miss read-only/named-rule phrasings and multiple genuine status/idea requests. FastAPI `/api/ask` tests verify that the exact-ID dated-trigger prompt reaches the unified source handler without ever calling the automation dashboard, while an explicit status inventory request continues to use the supported `automation-status` route.

After installing v0.18.415, submit the **same read-only exact-ID retry for 2967 and 3985**, including the safety phrase about disabled authorisation. Expect the dedicated `native_dated_trigger_discovery` evidence domain, `scanMode=targeted-rule-ids`, the two requested IDs and honest per-ID `readVerified` status. A successful native read may still show no verified `atDate#` field. This release fixes routing, **not** Rule Machine authoring permissions or dated-trigger persistence. Live installed acceptance and timing are not yet established.
