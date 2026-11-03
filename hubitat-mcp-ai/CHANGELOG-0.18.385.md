# v0.18.385 — MCP 5.1.5 Rule Machine thin-summary identity compatibility

## Source-backed compatibility defect
Upstream [MCP PR #576](https://github.com/kingpanther13/Hubitat-local-MCP-server/pull/576) and the 5.1.5 release now emit `namespace` directly in `hub_get_app_config(appId, summary=true)`. The full-page `app.appType.namespace/name` structure is separate and can cause app page code to execute. HomeBrain's read-only `native_rule_inventory_source._native_parent_from_summary` previously rejected an otherwise source-typed *thin* summary unless a nested `appType` dictionary was also present. This prevented the new server fix from resolving a Rule Machine parent when the built-in app-type catalog omitted that class.

## General fix
- Accept the **actual flat summary** only when its exact installed app ID, `type=Rule Machine`, `namespace=hubitat`, `user=false` and root-app relationship match the independent instance candidate; any supplied `appTypeId` must match.
- Preserve nested type evidence support. Reject contradictory nested class/name/namespace, non-built-in flags, mismatched app IDs, class IDs or explicitly conflicting catalog types; do not infer namespace from app names or labels.
- Continue using the existing **one extra non-rendering read-only summary** when a parent is unresolved. No new model round, form/page read, Rule Machine creation, scheduled switch operation or router change is added.
- Add synthetic tests for MCP 5.1.5 flat summary, real read-only inventory call shape and missing/contradictory identity refusal.

## Baseline and acceptance
Before: source inspection confirms a structurally valid MCP 5.1.5 flat summary would fail with `native-app-summary-class-namespace-unavailable` due to the missing nested object. After: offline synthetic fixtures accept that exact source contract and reject unsupported/conflicting records. **Installed MCP server version, native parent source receipt, dated-trigger execution and network-level effect remain UNVERIFIED**. Passing CI is not a real HomeBrain answer-quality score or a production Internet-blocker acceptance.

## Risk, safety, rollback
Change is restricted to native Rule Machine **read-only identity projection**. Existing user confirmation/write/backup boundaries, safety gates and the disabled native dated BAT remain unchanged. No live Hubitat/Home Assistant/OpenWrt action. Revert the runtime projector and version change if installed server summary format differs.

## Next
Update HomeBrain to v0.18.385 after green merge; ask the already specified **single read-only** `hub_get_app_config(appId=169,summary=true)` and installed MCP version question, and provide its full natural response + Technical Details JSON. Reconcile source ID/type/namespace before considering a separately approved new disposable virtual-switch dated BAT. Real blocking cannot be enabled from a published rule or virtual-switch OFF state alone.