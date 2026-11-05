# HomeBrainOS v0.18.419 — non-rendering parent read-only preflight

## Installed v0.18.418 finding

The 5 November 17:50 UTC live preflight confirmed MCP 5.1.6, native Rule Machine parent app 169 and built-in type 18, with 42 returned child rows and no modifying tool calls. However, its parent check called `hub_get_app_config(appId=169,includeSettings=false)`, a read-classified tool that upstream documents as rendering an app configuration page and executing page code. No observed modification was recorded, but absence of a mutating tool command alone does not prove that rendering an app page had no side effects. This conflicts with the strict no-editor-form/no-render intention.

## Change

- Remove full `hub_get_app_config` from native parent readiness verification. Use only `hub_list_apps(scope=instances/types)` and `hub_get_app_config(appId,summary=true)`, the latter being the fast, non-rendering `/installedapp/json` identity source.
- Retain exact app ID / `appTypeId` and native built-in type catalogue checks; require a source-reported parent-root record and at least one distinct returned child row with `parentId` matching that exact root. A label or `hasChildren` assertion cannot establish parentage. State `child_parent_relationship_unverified` if evidence is missing.
- Report only counts of returned linked children; never claim complete rule inventory. Keep safe parent diagnostics, date-guide limitations, and `readinessForMutation=false` unchanged.
- Tests require that **no** rendered configuration page is requested even on source conflicts, and verify no silent parent inference from root-only inventory.

## Upstream date contract clarification

Upstream MCP Server issue #575 was closed by PR #576, whose tests support `atDate#` as a native `date` input with `yyyy-MM-dd`. The installed `set_rule_reference` guide nevertheless does not enumerate the dated-trigger inputs. That missing guide declaration is a documentation/read-only schema coverage gap, not proof that installed dated creation or runtime execution has been validated. Native writes remain disabled, and no live dated trigger was created.

## Verification

CI and installed acceptance required independently. This release changes only read-only evidence paths; no Hubitat backup, rule, device, router, form write or permission changes.
