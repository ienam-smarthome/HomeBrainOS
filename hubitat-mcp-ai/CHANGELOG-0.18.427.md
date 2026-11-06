# HomeBrainOS v0.18.427 — evidence calibration for native authoring-contract reviews

## Live acceptance finding (5 November 2026)

Installed v0.18.426 correctly used the read-only rule-design-review route (2 model
rounds, 3 MCP calls, 19.172 seconds wall, unresolved) without modifying Hubitat.
However its prose table labelled multiple trigger, log action, year# and
prerequisite rows **Verified** while typed_authoring_contract remained
**checked-unverified** and evidenceComplete=false. A numbered log action
field placeholder was incorrectly presented as proof of calendar-year
semantics. The model also published a guide acknowledgement key, included
an unverified contract-shaped JSON sketch, and included a generic device/app
configuration disclaimer irrelevant to a runbook-only review.

## Changes

- Apply the same source-attestation boundary to markdown table statuses and
  structural JSON sketches as to executable native-rule proposals.
- Explain that year semantics, dated-trigger date/time encoding and scheduler
  execution cannot be inferred from a numbered form-field placeholder or
  a variable ISO example. Do not invent the missing native schema.
- Keep guide descriptions and upstream-tested/installed-runtime evidence
  separate; a successful guide call is not an upstream test receipt.
- Redact guide acknowledgement values from the read-only response while
  preserving the prerequisite that a valid acknowledgement may be necessary.
- Replace generic controller/device caveats with the contract-specific
  explanation, including when the model has already written a disclaimer.
- Emit explicit readinessForMutation=false in domain-specific investigation
  coverage and shared completion, including if a read-only review later
  collects a complete typed schema. Evidence of a schema never authorizes
  a write by itself.
- Regression tests replay the v0.18.426 false-verification table, JSON/key
  exposure, status conversion, no-write semantics, and unaffected true
  source-attested or unrelated motion-rule reviews.

## Safety and deployment

The change is confined to Answer Quality publication, read-only evidence
coverage, and tests. No new MCP operation, Rule Machine writer capability,
hub rule/device mutation, form render, confirmation or scheduler activation is
added. Native dated-trigger creation remains unverified and not authorized.

**Acceptance after CI and install:** Repeat the exact read-only MCP Rule Server
v5.1.6 runbook review. Require rule_design_review, evidenceComplete=false and
readinessForMutation=false without verified field claims, contract-shaped write
JSON, acknowledgement leakage, or unrelated app audit. Capture the actual
response and Technical JSON before measuring a quality gain.
