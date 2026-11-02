# Q1 real live verification — v0.18.371 native Rule Machine inventory

**Date of supplied response:** 2026-11-02 23:02 UTC. **Deployed app version reported:** `0.18.371` (user-provided Technical JSON; deployed Git SHA was not independently attested). **Scope:** one read-only response to the same inventory question used in v0.18.370. This is a source-bounded diagnostic observation, **not** a frozen-packet A/B nor a human-scored first-attempt accuracy baseline. Private raw hub tool payloads have not been stored in this repository.

## Source receipts and factual result

- Three successful non-mutating list calls read app instances (297 ms), app types (296 ms), and rules (270 ms).
- The extra `hub_get_app_config(appId=<candidate>,summary=true)` succeeded (81 ms), without native editor or form rendering. A fifth host-owned receipt projected the typed inventory, also non-mutating; these are **four upstream tool reads plus one derived receipt**, though the UI's `metrics.counters.tool_calls` is 5.
- The instance is Rule Machine-labelled with a positive app-type class ID; the returned type catalog contains **no matching source-typed native Rule Machine class**. The independent exact-ID summary did not provide `appType.namespace/name`. Therefore `parents=[]`, one candidate with `typeProof=unverified`, and a specific `native-app-summary-class-namespace-unavailable` proof gap.
- **Regression result:** `parentIdentityComplete=false` correctly captures the unresolved source type/instance join, replacing the falsely `true` value observed in v0.18.370. The independent `typesListComplete=true` describes only the returned type-page count, **not** native-class coverage. `investigation_coverage.questionResolved=false` and outcome `unresolved` consistently retain this gap. That is the precise correction this release intended.
- Both returned current app/rule lists were marked complete and no exact names ending `(One-time YYYY-MM-DD HH:MM)` matched. This absence scope cannot verify that any previous rule did/did not execute or get cleaned up. No rule/device mutation or confirmation was requested or reported.

## Performance and answer quality

| Observed single request | v0.18.370 | v0.18.371 |
| --- | ---: | ---: |
| Reported elapsed wall time | 3.237 s | 4.874 s |
| Source MCP reads | 4 | 4 |
| Derived inventory receipt | 1 | 1 |
| Independent app-summary read | 102 ms | 81 ms |
| Agent phase | 992 ms | 957 ms |
| Aggregate MCP HTTP | 971 ms | 938 ms |
| Model field | null | null |
| Native parent resolved | No | No |
| `parentIdentityComplete` | **true (incorrect)** | **false (correct)** |

**Measured at one case:** Metadata truthfulness (the targeted source-completeness assertion) is **verified by actual read-only installed response**. The answer is on-topic and explicitly describes the missing authority. It remains factually incomplete as intended, not a successful Rule Machine identity resolution. The changed end-to-end wall times cannot be attributed to the metadata change: provider execution, UI/network and host overhead are not controlled across requests. Median/p95, model reasoning improvement, general first-attempt accuracy and Claude comparison: **NOT MEASURED**. Do not treat the unchanged host-generated wording as a model-first narration success.

## Nonduplicative next milestone and safety boundary

Do **not** repeat the same live inventory read or change HomeBrain's answer wording to force resolution. The upstream installed server must expose the authoritative exact-ID native class source through a **non-rendering read-only contract**, e.g. projecting `getAppByAppId(id).appType.namespace/name` into the existing thin app summary with strict ID checking and no invented flags. See [upstream proposal](UPSTREAM-NATIVE-APP-IDENTITY-CONTRACT.md). Its `hub_export_native_app` is **not** a safe read-only fallback: upstream source explicitly states it instantiates and persists a cloner app, so never use it for this task. The linked upstream GitHub repository is pull-only; an attempted upstream issue write returned HTTP 403. No upstream patch is installed or filed.

One-time native rule creation remains disabled until independent source attestation of the parent and a persisted **dated** trigger/scheduling lifecycle contract, plus confirmation, backup, duplicate and post-write readback assurances. Resume Q2 *same-evidence* model comparison and other Answer Quality roadmap milestones rather than introducing a household-specific workaround.
