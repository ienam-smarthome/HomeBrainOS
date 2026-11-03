# v0.18.381 — exact MCP-owned device read, independent of Rule Machine exclusions

## Real installed failure

**2026-11-03 16:38 UTC, installed v0.18.380:** User requested only MCP-created virtual devices using `hub_list_devices(scope="owned",format="detailed")`, with a prohibition on Rule Machine calls. The response instead repeated the generic Rule Machine parent inventory: `hub_list_apps(instances)`, `hub_list_apps(types)`, `hub_list_rules`, `hub_get_app_config(169,summary=true)` plus local typed projection. **Zero `hub_list_devices` calls**. Wall 1.029s; five tool receipts, zero model rounds, no mutations. No owned device count or Virtual Switch absence was learned. **First-answer useful completion FAIL** for this real repeated request; not an official first-attempt benchmark datum.

## General failure and correction

The rule-inventory fast path uses broad topic/lookup regexes and has priority over an explicitly named, different device-only read. A safety sentence such as "Do not call any Rule Machine operation" must not select a Rule Machine investigation. v0.18.381 uses a strict **explicit source-request contract** for `hub_list_devices(scope="owned",format="detailed")` when the user requests device-only output. Route it before native rule inventory, and exclude it from rule auditing/final publication. A direct `hub_read_devices` gateway (or flat-mode `hub_list_devices` if exposed) is read-only, and only the requested owned scope may be queried.

The source reader performs bounded cursor pagination with count/total consistency, duplicate/ownership validation and explicit source errors. It never treats an absent or partial source as an empty owned inventory. Returned Virtual Switch identities use source-provided driver labels; `driverType` and `driverNamespace` are labelled unavailable when not provided, not fabricated. The shared coverage layer resolves only the requested owned-device inventory, **not** the native Rule Machine parent or delayed writer status. No new model rounds or writes.

## Offline tests, quality measurement and safety

A synthetic end-to-end agent test replays the user's exact original prompt and asserts only `hub_list_devices` is invoked, answer includes owned switch identities and typed completion is source-scoped. Separate tests cover pagination, complete zero rows, missing gateway, actual tool denial, inconsistent totals, missing MCP ownership, unavailable metadata and unchanged legitimate Rule Machine inventory routing.

**Baseline:** installed v0.18.380, 1.029s, five irrelevant read tools, 0 requested device reads, task FAIL. **After:** live v0.18.381 evidence NOT MEASURED; expected one owned-device read for a single page with 0 model rounds and correct result/coverage, or honest page-limited/permission error. Synthetic green CI does not prove installed performance or overall Q1/Q2 accuracy.

Production native delayed Internet-block writer remains **disabled** (`NATIVE_DELAY_ENABLED=False`); no virtual device or Rule Machine write is authorised. Native parent 169/type 18 remains unverified and must not be hardcoded. Roll back this explicit owned-inventory route if it intercepts multi-topic requests. Maintain permanent Answer Quality roadmap and zero live Hubitat/HA changes.
