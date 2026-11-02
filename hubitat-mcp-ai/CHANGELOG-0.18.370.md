# HomeBrainOS v0.18.370 — native Rule Machine parent identity from a second read-only source

## Live baseline and root cause

Installed 0.18.369, 2 Nov 2026 20:10 UK: **2.786s** wall; 3 successful MCP source reads (plus one derived receipt), zero model rounds, no writes or confirmations. Type-bound inventory listed a Rule Machine-labelled installed app **169**, `appTypeId=18`, but no `hubitat/Rule Machine` entry among the returned app-type classes (`nativeRuleMachineTypeIds=[]`). Both current rule/app lists reported zero exact `(One-time YYYY-MM-DD HH:MM)` matches. This is **not** evidence that dated one-time rule creation never existed.

The installed MCP server's `hub_list_apps(scope=types)` builds its list from community code plus best-effort built-in enrichment from `/hub2/appsList.systemAppTypes`. Upstream expressly warns that firmware/source failures can omit built-in classes despite successful `count`/list data. The earlier join treated that absence as definitive missing type identity. The provider also has a separate, **thin non-rendering** read via `hub_get_app_config(appId=N,summary=true)` hitting `/installedapp/json/N`.

## Improvement

For a read-only Rule Machine inventory only when the exact app-type join is unresolved, make **one** additional source-scoped `hub_get_app_config(summary=true)` read for the first candidate ID. Admit the native parent only if the raw hub reply:
- has the same positive app instance ID, `user=false`, compatible parent/type/instance class ID;
- explicitly contains `appType.namespace="hubitat"` and `appType.name="Rule Machine"`, with no system=false;
- does not contradict any listed app type with the same class ID.

A thin summary that reports only `{id,type,user}` **does not** establish native namespace: retain candidate status with `native-app-summary-class-namespace-unavailable`. An omitted built-in enrichment note marks the app-type catalog incomplete. Preserve type-ID conflicts and no-edit/no-write rules. Keep current exact-suffix absence scoped to complete current listings only.

## Verification / risk

Synthetic tests cover a source-attested native parent when the built-in type catalog is omitted, correct read-only second lookup, bare summary, false user/system, mismatched ID, conflicting class and namespace, no duplicate reads, source privacy and preserved zero-one-time-match scope. All existing tests and CI must pass. No native `create`, `form`, editor open, confirmation or Hubitat/HA mutation is enabled. The offline one-time native compiler remains non-executable.

**Actual installed v0.18.370 summary class shape, native parent verification and live latency are NOT MEASURED.** Upstream examples show the fast summary may omit `appType` entirely; the fallback is deliberately fail-closed rather than turning a label into write authority. A successful parent identity still does not prove dated one-time trigger and cleanup semantics. Rollback: revert this PR to v0.18.369.
