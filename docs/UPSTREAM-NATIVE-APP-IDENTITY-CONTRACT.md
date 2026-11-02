# Upstream native application identity source — read-only compatibility contract

**Scope:** upstream Hubitat-local-MCP-server (not HomeBrain's answer wording). **Status:** proposed, NOT implemented or tested on an installed server. No live hub writes and no native one-shot creation.

## Evidence and reason

A read-only installed v0.18.370 HomeBrain trace from 2026-11-02 has a Rule Machine-labelled parent candidate with a positive instance class ID, but its complete returned type rows lack that class. An extra successful `hub_get_app_config(appId=N,summary=true)` has only the bare identity, without `appType.namespace/name`. Its output cannot establish the native writer parent. HomeBrain correctly keeps the candidate unverified rather than trusting a display label or `user:false`.

Source review of public upstream `kingpanther13/Hubitat-local-MCP-server`:

- `libraries/mcp-code-management-lib.groovy` `toolListHubApps`: user code classes come from `/hub2/userAppTypes`. Built-in classes are best-effort enrichment via `/hub2/appsList.systemAppTypes`, which can be omitted even while the returned user type rows are count-complete.
- `toolGetAppConfig` `summary=true`: the exact `/installedapp/json/<id>` object is parsed and passed through; the thin response can lack native class namespace/name. It does not render the native editor.
- `libraries/mcp-native-documents-lib.groovy` `toolCreateRuleDocument`: before creation, source code explicitly verifies `getAppByAppId(parentId).appType.namespace == 'hubitat'` and `.name == 'Rule Machine'`. A **read-only verification of these same platform identity fields** is the missing source contract.

## Proposed upstream change (illustrative; needs upstream tests)

Extend `hub_get_app_config(appId=N,summary=true)` only with exact-ID platform-sourced metadata. The server should obtain the installed object with `getAppByAppId(N)` **without rendering a configuration page**, then source-project a minimal `appType` object when and only when the platform returns positively attested fields:

```groovy
// Pseudocode, not a deployable patch.
def object = getAppByAppId(requestedId)
if (object?.id?.toString() == requestedId.toString() &&
    object?.appType?.namespace &&
    object?.appType?.name) {
    summaryResult.appType = [
        namespace: object.appType.namespace.toString(),
        name: object.appType.name.toString()
    ]
    // Include type ID / system flag only if independently supplied.
}
```

Do not manufacture namespace, status, type ID or a system flag from a bare label or `user:false`. A contradictory existing type record must not be silently promoted; clients should fail closed. If the platform lookup is missing or fails, return explicit **class-unverified** metadata (or omit `appType`) while preserving the original successful thin identity read. Never expose settings, secrets or unrelated app objects.

## Required upstream regression tests

1. Exact-ID native installed `hubitat/Rule Machine` returns typed namespace/name, no form rendering.
2. A built-in lookalike display name or `user:false` **alone** never qualifies.
3. Wrong ID, failed source, missing class fields, community class, and explicit catalog conflict do not gain native authority.
4. Existing `/installedapp/json/<id>` pass-through and error paths continue working.
5. No `/installedapp/configure/json` render, editor `open`, `Done`, rule creation, child installation or device command.
6. If the native platform object cannot reliably supply class identity on particular firmware, report that source gap instead of guessing.

The linked GitHub integration has **pull-only** upstream access; the attempt to file a public upstream issue returned **403 Resource not accessible by integration**. This repository document preserves the exact proposed contract without asserting submission or upstream merge.

## Downstream acceptance

After a verified upstream and installed-server update, repeat the same read-only Rule Machine inventory question with Technical JSON. HomeBrain's existing strict source-typed summary admission may then verify the root, provided **matching app ID, built-in status, namespace/name, compatible type IDs, and absence of conflict**. A verified parent identity alone is not authority to write: also require a source-proven **dated** native trigger contract, lifecycle semantics, duplicate/backup/confirmation safety and typed post-write readback. The original 40 frozen Answer Quality cases remain unchanged. Actual source-backed answer quality and new latency remain **NOT MEASURED**.
