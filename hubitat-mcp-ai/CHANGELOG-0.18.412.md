# HomeBrainOS 0.18.412 — read-only existing native dated-trigger discovery

## Installed 0.18.411 failure, 5 November 2026

User requested a strict read-only search of **already-existing Rule Machine rules** for the "Certain Time (and optional date)" trigger; if found, inspect stored `time#`, `atTime#`, `date#`, `atDate#`, types, values and date enablement. No rule creation, no native form-open, no device command.

Installed 0.18.411 instead ran **40.751 seconds**, **10 free Gemma Cloud rounds**, six nonmutating MCP calls (provider 36.552s) and classified the request as `existing_rule_verification`. It selected app 4163 "Block Nest hub from 5.50pm" without proving that rule has a dated trigger, used `hub_get_app_config(summary=true)` and a full configuration read, plus health/log reads, and ended with an unrelated generic action-tree, exact-name-duplicate and inactivity-controller report. Technical JSON returned no typed date-field values and did not establish that no dated rules exist. This is a scope/evidence failure, not proof of missing date functionality.

## Source discovery

Upstream installed-app inventory `hub_list_apps(scope=instances,filter=children)` returns app IDs, native type name and parent ID in pages. The upstream `hub_set_rule(operation=read,rule_id,args:{sections:[triggers,settings]})` reads native state and typed settings **without rendering the editor**, unlike native form-open operations which may execute app code. Upstream server v5.1.5 release tests cover native `time#` / `atTime#` / `date#` / `atDate#` typed input contracts, but tests are not actual user-hub persisted-readback proof.

## Correction: bounded host-owned read-only workflow

- Recognize a **positive read-only existing dated-trigger search** before broad existing-rule/action-tree routing. "Do not create a test rule" is a restriction, not a request to create one. No model/tool-discovery inference rounds are required for this narrow source task.
- Read up to four installed child-app inventory pages, retaining source IDs only for built-in `Rule-5.1` child instances. On a named offset, scan a bounded batch of at most 12 eligible IDs, sorted by ID; report how many candidate IDs were inspected and whether further pages or candidates may remain. Never infer whole-hub absence from a partial page, hidden apps or an unsuccessful read.
- Use only exact-ID `hub_set_rule(operation=read)` with `sections=["triggers","settings"]` through an approved read-classified native gateway. No `hub_set_rule(operation=form/update/create)`, no `hub_set_native_app`, no UI form rendering, no write flag or confirmation token.
- Retain only bounded allowlisted date/time fields and source types for matching trigger-row IDs. An enabled dated field is accepted only with a validated `date#=true`, syntactically and calendar-valid `atDate#` of type date, corresponding time and atTime fields of their respective types, plus a native trigger row for the same allocated ID. Distinguish source-observed *stored settings* from actual rule firing, calendar scheduling or one-time semantics.
- Stop at a positive matching existing rule or after at most 12 native document attempts. If a match is absent in this bounded batch, report an **unresolved** finding and offer the next numeric scan offset. No absence claim is permitted. Any malformed, truncated, mismatched, sensitive or unreadable source stays unverified.
- Publish `typed_native_dated_trigger_fields` (per ID) and `typed_native_dated_trigger_discovery` receipts; shared completion retains `domain=native_dated_trigger_discovery` instead of overwriting with `existing_rule_verification`. No extra MCP calls are added to *other* question types.

## Safety and limits

No rule, hub, device, router or backup settings change. No native authoring permission, date-trigger writer gate, or >=5.1.6 version threshold change. A found saved date field does **not** grant native Rule Machine writer access, prove runtime scheduling or establish that the rule executes only once. The scanner only sees visible, returned built-in child apps; it is explicitly not an exhaustive negative audit unless a separately validated full source is available.

Tests replay the exact failing prompt; verify saved fields, date toggle, invalid dates, disabled date, mismatched IDs, redacted unrelated settings, safe source-only operations, 12-rule bound and continuation, unavailable native reader, and finalization scope.

## After-update acceptance

Upgrade HomeBrainOS to 0.18.412. Re-run the identical existing dated-trigger read-only prompt and inspect the answer plus Technical JSON. Expect `native_dated_trigger_discovery` coverage, source-type details (or a bounded no-match with next offset), no unrelated inactivity-controller audit, and no mutation receipt. Live performance and availability of a suitable dated rule remain unmeasured.
