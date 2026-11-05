# HomeBrainOS v0.18.411 — preserve native Rule Machine read-only preflight

## Installed v0.18.410 failure (5 November 2026)

The user requested a read-only preflight for dated one-time Rule Machine authoring: compare MCP initialize/serverInfo with hub_get_info, inspect the installed writer guides and atDate# date contract/readback, check the latest hub-local backup, and refer to the previously verified native parent app 169.

The deterministic preflight recorded **typed_native_rule_readiness** with MCP Rule Server version **5.1.5** (initialize only), latest backup **2026-11-05T03:02:31+00:00** (24 returned hub-local records), and both rule guide sections readable. It correctly set preflightEvidenceComplete=true and readinessForMutation=false. Three read-only MCP source calls plus one local projection took 0.658s agent phase / 3.413s total with no model round.

However, the generic shared completion reclassified the original mixed request as app_class_identity because of the mention of parent app 169. That postprocessor erased the preflight answer with "Native class identity: not independently verified". This was a **completion-domain precedence defect**, not a failure of the separately verified app identity or hub.

The independent hub_get_info version read, atDate# supported field declaration, and saved-date readback were not verified by that run.

## Generalized no-write correction

- Give source-typed read-only native Rule Machine readiness precedence over generic app/parent identity classification at shared completion, preserving both partial and complete readiness answers. Never create a new model round or call Hubitat during this final step.
- When the request explicitly asks for initialize vs hub_get_info agreement, add one read-only hub_get_info source check and project its mcpServerVersion. A basic three-source preflight remains three source calls.
- When the question asks about dated one-time fields, inspect the already-read set_rule_reference guide for an explicit atDate# type=date yyyy-MM-dd declaration. A guide merely being readable does not establish date support. A date declaration is documentation evidence only, not a saved-rule readback.
- Keep core preflight completion distinct from full requested proof. Report separate version-agreement and date-field/readback requirements when requested; mark absent or conflicting evidence unverified rather than claiming all requested authoring checks passed.
- Never disclose rotating guide acknowledgement keys. No rule, device, router, backup, confirmation, write permission, or native writer gate changed; readinessForMutation remains false. HomeBrain's >=5.1.6 dated writer version threshold is unchanged until independently verified installed contract and writer conditions justify review.

## Tests and post-install acceptance

Regression tests replay the exact cross-domain user question, assert the answer is the native preflight (not an app-identity fallback), source version agreement and conflicts, missing guide declaration and date readback, acknowledgement-token nonpublication, and the unchanged simple three-call preflight budget.

After deployment repeat the same read-only preflight; verify investigation_coverage.domain=native_rule_readiness and distinguish the completed core source checks from still-unverified date authoring/readback. CI passing cannot establish actual native date-trigger writing or justify creating a test rule.
