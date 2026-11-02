# HomeBrainOS / Hubitat MCP AI v0.18.366 — source-complete native existing-rule reads

## User-observed v0.18.365 regression (2026-11-02)

First-shot read-only native Rule Machine inspection, named rule 4136, **43.586s wall / 42.095s agent / 39.829s Ollama provider, five model rounds and five nonmutating tools**. No confirmation or hub change (v0.18.365 effect-classification fix verified live), but the result was **Unresolved** and returned a partial list of `hub_get_app_config` settings rather than the actual native rule document. One model-proposed write was blocked (safe but unproductive). A prior successful `hub_set_rule(operation=read)` proved the installed native source is available. The model-facing read-only tool view deliberately excludes all `hub_manage_*` gateways; passive discovery cannot safely allow one mixed read/write gateway, so the model never obtained the complete source.

## Q1 source-complete evidence change

- For an **explicitly named, existing Rule Machine rule** being verified read-only, a host-owned source prefetch selects an installed native gateway and makes exactly one validated `hub_set_rule(operation="read",rule_id=...)` call. The management gateway **is not added to the model's read-only tool surface**. No `confirm`, `form`, `create`, `update`, or other gateway sub-operations are sent.
- The source response must match the requested rule ID and include typed native settings, trigger map, ordered action rows and condition map. Bad ID, malformed/truncated document, unsupported or sensitive native settings fail closed. Redact/suppress unsupported fields; never treat an incomplete document as fully verified.
- Preserve a bounded source-typed receipt (including native rule time, action methods, selected devices, and available health booleans) and pass it to the model for natural synthesis. Existing-rule source coverage admits **stored logic** only when the complete, target-matched typed projection is present; the existing claim calibrator then retains the model narrative. On read failure/unavailability, fall back to the existing partial readers.
- Avoid two unnecessary health/variable prefetches and the generic app configuration prefetch when the native document is source-complete.
- Add synthetic regression cases for trusted native source, missing gateway, source failure, wrong ID, incomplete/truncated/secret fields and source-aware completion. No live Hubitat or HA changes during development.

## Limits, measurement and safety

Native document read proves stored configuration but **not actual runtime execution**, a parent link, a dated one-shot trigger, or post-execution disablement. The separate native Rule Machine **create** compiler remains disabled. Target first-attempt read usefulness and end-to-end latency improvements are **not yet live measured**: CI confirms structural/factual evidence admission, not model accuracy. Compare live v0.18.366 Q&A against the captured v0.18.365 original question on the same installed hub and model; do not claim a percentage or Claude equivalence without reviewed cases.

Rollback: revert this release's source prefetch/coverage changes, retaining the v0.18.365 exact-read effect policy.
