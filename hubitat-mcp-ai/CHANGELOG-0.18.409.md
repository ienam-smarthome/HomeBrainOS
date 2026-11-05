# HomeBrainOS 0.18.409 — read-only instance-to-type catalog correlation

## Installed v0.18.408 source investigation

At 10:11 UK time on 5 November, an installed 0.18.408 user-run identity investigation for an installed Hubitat app completed in **28.661s**, **8 free Gemma model rounds**, **4 read-only MCP calls** and **24.483s provider time**. The user requested exact numeric ID correlation. The model selected:
- hub_list_apps(scope=instances) and a filtered scope=instances read
- filtered hub_list_apps(scope=types) read
- hub_get_app_config(appId=169, summary=true)

Technical JSON reported the inventory reads only as field-name summaries; its only typed identity receipt was the app-configuration summary containing the reported type, namespace and user flag. There was no published numeric appTypeId or type-catalog record ID, so the final class/parent identity correctly remained **unresolved**. The new request has a different SHA than the previous shorter question, so timings are not a controlled version benchmark.

## Upstream capability

Hubitat-local-MCP-server v4.7.1 added appTypeId to hub_list_apps(scope=instances) rows (upstream issue #526 and PR #527). Each instance row is sourced from Hubitat /hub2/appsList; scope=types contains app-type IDs with system/isBuiltIn and namespace fields. These are upstream code contracts, *not* proof that the installed server and hub return the same fields for this user's target instance.

## General read-only change

- Successful, explicit name-filtered hub_list_apps(scope=instances/types) reads now produce bounded typed receipts with up to 20 safe returned rows. An unfiltered whole-hub page or unexpected type-catalog source does not receive the projection.
- Source-reported instance fields: exact appId, numeric appTypeId if present, safe name/type, user and explicit parentId. Type-catalog fields: exact typeId, name, namespace, boolean system/isBuiltIn.
- Join an app instance to a catalog type **only by matching positive numeric IDs** from source-typed receipts; never by display name. A same-name community type is not a match for a different ID. Missing type IDs, conflicting source values, absent filtered pages or catalog failure remain incomplete and do not prove absence.
- Shared answer publication uses the same current-turn read-only receipts to report source-reported IDs and their catalog match, clearly distinguished from native parent certification. The instance-to-type obligation can be marked observed only with a target-matched numeric instance type ID. Native class/parent verification remains unresolved unless a separately validated authoritative class contract is available; **native Rule Machine writing remains fail-closed**.
- New Technical JSON fields include typed_app_inventory_page and typed_app_type_catalog_page receipts and appIdentityCorrelation with exact reported IDs, match status and nativeClassBindingVerified=false.
- No additional inference rounds, MCP requests, data mutation, writer permission or device/rule changes.

## Validation / acceptance still required

CI tests cover raw tool results through receipt publishing, source tags and redaction, conflicting and missing numeric IDs, duplicate names, type-catalog classification, wrong target, pagination limits and conservative native proof. A new installed read-only run is needed to check whether the live MCP response actually supplies appTypeId in the filtered instance row and an ID-matching type record.

No performance gain, type ID value, built-in parent verification or release deployment is claimed from offline tests.
