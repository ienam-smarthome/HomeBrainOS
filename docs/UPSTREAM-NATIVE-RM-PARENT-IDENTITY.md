# Upstream request: source-attested native Rule Machine parent class (read-only)

**2026-11-03 · Dependency preparation, no live writes**

## Source evidence and scope

The installed HomeBrainOS native inventory returns one Rule Machine parent *candidate*, but cannot identify its native built-in class. It has an instance appTypeId yet the built-in type record is absent from `hub_list_apps(scope="types")`. The source-typed `hub_get_app_config(summary=true)` response also omits `appType.namespace/name`. **Do not elevate a parent candidate based on the app label, hardcode any ID, or treat missing type records as empty.**

The upstream source for this gap is `libraries/mcp-code-management-lib.groovy` in `kingpanther13/Hubitat-local-MCP-server`. In `toolGetAppConfig(args)`:
- `summary=true` returns the hub's cheap `/installedapp/json/<id>` response almost verbatim; it does **not** render the native app page.
- Full configuration mode uses `/installedapp/configure/json/<id>` and already receives `parsed.app.appType`; the MCP projection currently exposes only `system` and `menu` from that map, losing any source-provided `name`, `namespace`, and native type `id`.
- `src/test/groovy/server/ToolGetAppConfigSpec.groovy` includes a fixture with `appType: {name: "Rule Machine", namespace: "hubitat", system: true, ...}`. This fixture demonstrates a **possible** platform payload shape, not a verified source shape on every firmware version.
- `hub_list_apps(scope="types")` reads community code from `/hub2/userAppTypes` and enriches built-ins from `/hub2/appsList.systemAppTypes` **only when the latter is supplied**. A successful, count-complete types page can therefore still omit the specific native class.

The separate upstream [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) requests `atDate#` support and mentions the summary class-identity gap. **The triggerless Delay → OFF candidate does not require date-typed native triggers.** Source-attested parent identity is the actual blocker.

## Minimal upstream change proposal

Prefer a targeted read-only class identity operation or an **opt-in** mode on `hub_get_app_config`, to avoid silently making `summary=true` render a potentially expensive native app page. A conservative first step is to retain exact source-returned `name`, `namespace`, and `id` **if present** in full config's `app.appType` projection, alongside the existing `system/menu`. Never infer a namespace from the installed app label, `user=false`, an app count, or an unresolved class ID.

Suggested *illustrative* Groovy change in the full configuration result construction (must be adapted and tested upstream):

```groovy
def appTypeRaw = parsed.app.appType
def publicClass = null
if (appTypeRaw instanceof Map) {
    publicClass = [system: appTypeRaw.system == true, menu: appTypeRaw.menu]
    ['id', 'name', 'namespace'].each { k ->
        if (appTypeRaw.containsKey(k) && appTypeRaw[k] != null) {
            publicClass[k] = appTypeRaw[k] // native source only; no defaults
        }
    }
}
def appObj = [
    id: parsed.app.id,
    label: stripAppConfigHtml(parsed.app.trueLabel ?: parsed.app.label),
    name: parsed.app.name,
    appType: publicClass,
    disabled: parsed.app.disabled == true,
    parentAppId: parsed.app.parentAppId,
    installed: parsed.app.installed == true
]
```

**Important:** The current client cannot use this proposal until upstream implements and releases an appropriate typed read surface and HomeBrainOS gains a narrowly scoped read-only consumer. A generic full-config read may execute Hubitat's dynamic page-rendering code; any fallback must be strictly opt-in, read-only, time-bounded and not triggered by casual Rule Machine questions. No `hub_set_rule(operation="form")`, no create/update, and no automatic retries of ambiguous writes.

A stronger upstream API can return only:
```json
{
  "success": true,
  "appId": "<requested numeric ID>",
  "appType": {
    "id": "<only if native payload provides it>",
    "namespace": "hubitat",
    "name": "Rule Machine",
    "system": true
  },
  "source": "/installedapp/configure/json/<same app ID>"
}
```
The example values are **acceptance-shape examples, not a claim that any specific hub already returned them**. If the source lacks any field, return a missing-field indicator rather than synthesising it. Never reveal credentials or unrelated app settings.

## Upstream acceptance tests

1. Source fixture has exact native class `namespace=hubitat`, `name=Rule Machine`, `system=true`; the read returns those **source-provided** fields with matching app ID and no other app or setting data.
2. Native `namespace` missing, type name missing, wrong namespace, `system=false`, or mismatched requested app ID: no verified class identity, no writer authorization.
3. `hub_list_apps(scope="types")` returns complete community types but omits `systemAppTypes`: the client must remain unresolved unless a separate typed source proves identity. A community type with the same name and class ID must never be promoted.
4. `summary=true` remains cheap and compatible; any deeper native config page read is explicit and bounded.
5. Verify the read master permission gate, gateway/flat tool parity, sensitive-value redaction, empty/unreadable source failures and **zero modifying calls**.

## HomeBrainOS safety status and ownership

- The offline delayed-rule candidate additionally requires `namespace="hubitat"` and `system=true`, `isBuiltIn=true`, `allowNewInstances=true` from the exact matching type row; all missing or contradictory evidence fails closed. New regression tests cover community, empty and missing namespace.
- The candidate is **not installed or enabled**: `NATIVE_DELAY_ENABLED=False`. No existing MCP-owned switch may be reused or modified without separate approval.
- Actual native parent proof remains **not verified**; even an upstream improvement requires installed read-only acceptance before a separately authorised disposable virtual-switch BAT.

## Contribution constraint

The repository connector can read the upstream project but receives **403 Resource not accessible by integration** when attempting to create an upstream branch or comment on issue #575. This document is therefore a source-backed handoff and copyable implementation specification, **not an upstream PR or claim that the developer was notified**. A maintainer or an account with write/comment access must submit it upstream. Until the upstream endpoint is available, HomeBrainOS must remain blocked rather than invent identity.

## Answer Quality charter

This is a general, source-identity safety dependency, not an incident-specific fix, an Answer Quality score gain, or evidence that Internet blocking is ready. The primary Q1/Q2 evidence-based first-answer benchmark remains active. No change to the runtime add-on version, Home Assistant or Hubitat.
