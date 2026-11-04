# v0.18.387 — distinguish an absent built-in app-type namespace from an explicit conflict

## Real observed evidence (2026-11-03, installed v0.18.386)

The **same read-only Rule Machine inventory question** returned in **3.611 seconds** rather than **25.650 seconds** on v0.18.385. The previous six Gemma 4 31B model rounds fell to zero; logical read tools fell from ten to five. This is an **observed 85.9% shorter elapsed time for one paired question**, not an accepted population latency metric or a certified first-attempt quality result (`first_attempt_verified=false`, `deployed_build_sha_verified=false`).

The typed inventory reader established candidate parent app ID 169, appTypeId 18; a complete exact-suffix scan found zero one-time-named rules. The additional `hub_get_app_config(appId=169,summary=true)` read succeeded in 82ms, but the parent remained unverified with `native-app-summary-catalog-conflict`. The public receipt **did not include the actual matched app-type catalog row** or raw thin-summary fields. Thus the precise live contradiction's content is not independently established from this receipt.

## Source-contract defect and generic correction

The upstream [Hubitat MCP type listing](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/main/libraries/mcp-code-management-lib.groovy) combines community `/hub2/userAppTypes` rows and built-in `/hub2/appsList.systemAppTypes` rows. Its projection supplies `system` and `isBuiltIn` flags for each type. Built-in system types may **omit `namespace`**. The independent MCP 5.1.5 thin installed-app summary reads the source-observed native namespace via `getAppByAppId(...).appType.namespace`.

HomeBrain's prior confirmation path treated any catalog row whose `namespace != "hubitat"` as a contradiction, **including an absent namespace on an otherwise built-in row**. This improperly vetoes independently typed installed-app evidence. v0.18.387 distinguishes an *absent* namespace from an explicitly *different* one, while retaining contradictions for mismatched class name, explicit non-Hubitat namespace, `system=false` or `isBuiltIn=false`. The native catalog-only join now refuses explicit user-code flags even if the namespace string is misleading. An independent summary is still necessary to attest `namespace=hubitat` when the built-in catalog omitted it.

A bounded `catalogClassConflicts` diagnostic contains only class ID, whether the class name matches, coarse namespace status and source boolean flags—never arbitrary third-party app names or raw inventory. The same read-only MCP operations run, with no additional model rounds or tools. The **offline-only, disabled** dated BAT parent helper also no longer refuses a built-in type solely because the catalog omits namespace: it demands an exact independent `summary=true` attestation before any hypothetical write. Explicitly non-native class flags and root/ID conflicts still refuse. No production BAT enablement or added runtime tool calls.

## Offline tests and limitations

Synthetic tests cover (1) a system built-in class with missing namespace plus a correctly typed independent summary, (2) explicit foreign namespace, wrong class name or false built-in flags, (3) redaction of unrelated type names, and (4) no catalog-only admission from an explicit user-code type. Existing source/answer routing, strict ID join, first-request authorization and write protections are preserved.

**Pre-change real source class row was not present in the public JSON**: the namespace-omission explanation is verified against upstream source semantics but not proved as the exact deployed data. **Post-install native parent acceptance, scheduling, dated BAT operation and router enforcement remain NOT MEASURED.** Do not claim success or authorize an Internet-blocker write merely from green tests. No live Hubitat, Home Assistant or OpenWrt changes.

## Safe next verification

After v0.18.387 is installed, repeat the exact same read-only inventory question and supply the answer/Technical JSON. If the native parent remains unresolved, inspect only the bounded new `catalogClassConflicts` fields rather than guessing or trying a write. Any one-time Rule Machine/virtual-switch BAT requires independent backup, verified native parent, exact device identity and **separate explicit user approval**, and still does not prove an actual network-level block. Revert this PR if existing native class identity checks regress.
