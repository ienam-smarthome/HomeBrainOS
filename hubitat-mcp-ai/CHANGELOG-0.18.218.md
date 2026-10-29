# Hubitat MCP AI v0.18.218 — Generic source-prefix candidate frontier

## Live v0.18.217 regression (29 October 2026)

A model-selected `homebrain_find_device(name="bathroom")` returned six ambiguous matches after approximately 11ms; no candidate IDs were individually authorised, so three model-selected `hub_get_device` READ proposals were rejected as `target_id_not_verified_from_live_source`. The model then proposed an unscoped `hub_list_devices` that timed out after 20,003ms. No successful MCP reads were obtained. Six model/identity rounds? **Four model calls** consumed 16,975ms; total duration **37,002ms**. Importantly, the v0.18.217 subject-relevance guard correctly *withheld* unrelated health findings instead of fabricating an answer.

## Reusable correction

- A model-selected, authoritative live name lookup yielding **several different source-name prefix matches** now returns `candidate_group` (at most eight), with individually attested device IDs and names. For example, a single location/name prefix can refer to independent Light, Meter, Fan and Switch labels. No auto-selection or inference of true room membership, device capability, current state or relevance. Exact-name collisions remain `ambiguous`, with no automatic target permission; large prefix matches remain explicitly too large with no truncated authority.
- Existing Native V2 READ-only authorization can now admit a **model-chosen** targeted `hub_get_device` for any live attested candidate, but still refuses fabricated/unverified IDs, retains independent field/effect/schema enforcement, and does not initiate a read without model selection.
- After the model has a bounded source-attested candidate group, V2 declines an **unscoped full-device inventory** proposal and returns a concrete suggestion to read the already returned IDs separately. This avoids the observed 20-second broad-list timeout *for this scope*; whole-hub questions without such candidates retain their ability to list devices normally.
- The generic subject-relevance guard reports incomplete candidate coverage rather than presenting unrelated facts as an answer. Six independently verified candidates do not mean the user meant all six; each must be examined and uncertainty must remain explicit. The full technical record still shows all rejected calls.
- Nine new regression tests cover six-source lookup, unrelated name prefixes, exact-name collision safety, group upper bound, unverified ID refusal, partial device-state coverage, no forced reads, no unscoped-list fallback and independent wide inventory behaviour.

This remains experimental Native MCP READ-only. No Hubitat device, rule, automation, production Main Ask, write permission or model command authority is changed. It does not claim the user's actual bathroom devices were read; the uploaded trace established only six identity matches without showing their names.

## Limits

Performance and task fulfilment require a new live run after updating the add-on. Candidate names are not proof of group membership, and the model must still choose sufficiently discriminating reads within its configured budget. Further architectural work includes source-attested room membership projection, reusable multi-entity answer synthesis and improvement of model tool selection rather than per-question routing.
