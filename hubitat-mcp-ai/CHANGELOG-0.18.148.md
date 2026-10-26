# HomeBrainOS v0.18.148 — V2 primary-subject matching

The full Bedroom 3 Mesh investigation question still failed on .147 with
HTTP 422, listing two conflicting inventory IDs (#5381 and #7776), even
though Bedroom 3 Mesh is independently known as device #7103.

## Cause and correction

The former automatic resolver scanned the **entire question** for every
Hubitat label and underlying name, then aborted on **any** same-strength
ambiguous match, including technical nouns that appear as contextual
instructions after the original subject. The .147 label-vs-generic-name
precedence fix could not address collisions between unrelated aliases.

- A unique **complete multiword Hubitat friendly label** now acts as the
  identity anchor. Lower-confidence incidental aliases cannot introduce
  another target or veto that verified subject just because they occur
  later in the question.
- Multiple distinct independently anchored friendly-label names are still
  preserved as multiple devices for explicit comparison cases.
- **Ambiguous aliases before the first verified subject, and identical
  best-priority labels for the actual named subject, still fail closed.**
  V2 does not choose arbitrarily among duplicated device identities.
- If a question lacks a strong named subject, it retains the strict
  existing ambiguity checks and optional Advanced override.
- Fixed the diagnostic formatting regex that incorrectly stripped most
  characters from valid candidate names, displaying "Device (#ID)".
  On future ambiguity errors the result includes sanitized inventory
  labels/IDs **and the matched question phrase**.
- Same mechanism applies to normal question matching and the .146
  semantic-timeout fallback. No new model/classifier permission.

Tests reproduce the **entire user-supplied long question**, including
different synthetic devices whose generic names or friendly labels match
unrelated later text. Additional tests cover duplicate primary names,
ambiguity before the primary, multi-device questions, AI name proposals,
and explicitly verified ID overrides. This synthetic coverage does not
identify the actual live Hubitat names of #5381 and #7776.

This remains a best-effort, deterministic entity resolver. Questions with
several named targets and contextual references can be semantically
ambiguous; V2 must retain its verified-ID boundary. The change is scoped
to opt-in read-only Investigation V2. Production V1, Hubitat devices and
automations are unchanged.
