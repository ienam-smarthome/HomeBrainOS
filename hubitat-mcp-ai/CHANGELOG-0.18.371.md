# HomeBrainOS v0.18.371 — distinguish native-parent identity proof from row completeness

## Installed first-shot source evidence (v0.18.370, 2026-11-02)

One read-only native Rule Machine inventory response took **3.237 seconds** wall, had **four successful nonmutating upstream MCP reads** (instance list 320 ms; app types 316 ms; rule list 240 ms; exact-ID app summary 102 ms) and one derived source projection; no model rounds and no writes/confirmation. The Rule Machine-labelled candidate has instance ID 169, class ID 18, but the returned app-type rows have **no matching native class ID**; the independent `hub_get_app_config(summary=true)` is successful yet omits `appType.namespace/name`. Therefore native parent identity remains unverified. Complete current rule/app lists had zero exact dated-name suffix matches, not proof that an older one-time rule never ran.

**Problem:** The typed projection reported `parentIdentityComplete=true` because the *count of returned type rows* was complete, while it simultaneously returned an unverified candidate parent and `investigation_coverage.questionResolved=false`. Count completeness cannot supply a missing namespace/class proof. This is a general source completeness invariant, not a private app ID mapping or incident-specific answer phrase.

## Change and impact

`parentIdentityComplete` now remains **false whenever candidate parent IDs are unresolved**, including complete-page/no-matching-class and missing summary metadata. A proven source-typed parent remains complete even if the unrelated built-in class type catalog omitted its enrichment. Complete lists without any candidates retain their existing factual absence scope. The rule list, model answer, four-read fallback, read-only permissions and native rule writer are otherwise unchanged. Tests include precisely the mismatch between count-complete type rows and missing class join, bare summary, conflicting type, verified native parent and complete no-candidate inventory.

## Upstream blocker and handoff

The installed Hubitat MCP server does not expose native class metadata via either current read-only source. Upstream source already checks `getAppByAppId(parentId).appType.namespace/name` inside its **writer**, but `hub_get_app_config(summary=true)` currently passes through `/installedapp/json/<id>` and can omit those properties. See [upstream source contract proposal](../docs/UPSTREAM-NATIVE-APP-IDENTITY-CONTRACT.md) for a small nonrendering read-only identity projection and negative tests. The linked GitHub connector has upstream **read-only** repository permission (issue creation returned 403), so no upstream fix/issue is claimed.

**No native one-time creation restoration:** `parent_id`, installed dated trigger semantics, consent and exact post-write readback are still unverified for native authoring. Never retry the expired 2026-11-02 15:35 action or create a form shell. This release does not enable that capability.

## Answer Quality measurement

One actual v0.18.370 example establishes the metadata contradiction and the 3.237-second response, not a paired same-evidence pre/post benchmark. v0.18.371 improvement is **synthetically verified evidence-completeness fidelity only**; real first-answer grounding, natural explanation, latency, provider/model comparison and one-time authoring remain **NOT MEASURED**. No Hubitat or Home Assistant operations were made during development. Revert the projection flag and regression tests if a source-completeness contract regresses; never replace missing metadata with name-based proof.
