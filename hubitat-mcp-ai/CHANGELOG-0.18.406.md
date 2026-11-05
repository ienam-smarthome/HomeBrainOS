# HomeBrainOS v0.18.406 — auditable, read-only app instance metadata

## Observed acceptance of v0.18.405

The user reran the original native Rule Machine parent identity question on the
reported installed version **0.18.405** on 2026-11-05 UTC. The answer
correctly focused on app-class identity rather than unrelated rule-action
certification, and it kept native parent identity **unresolved**.

- **22.568s** end to end, **5 Gemma Cloud rounds**, **3 read-only MCP calls**,
  compared with one pre-update sample of 33.825s / 7 rounds / 4 calls.
  This is an observed **11.257s** difference, not an independently controlled
  performance improvement or production benchmark.
- The coverage contract correctly identified app_class_identity, and both
  instance_identity and native_class_binding remained checked-unverified.
  No write was recorded.
- The natural-language answer nevertheless said the label/name were verified,
  described the source-reported native namespace, system/root status, and
  returned 42 child rules. The public MCP evidence receipts displayed only
  response field **names**, so these individual scalar claims were **not
  independently auditable from the published Technical JSON**. This does not
  prove the model invented the values: it may have seen the raw MCP result.

## Generalized correction

- For an explicitly target-ID-scoped, successful read-only
  hub_read_apps_code / hub_get_app_config result, retain a bounded typed
  projection of the returned app's exact matching id and appTypeId.
  Optionally retain safe source-reported label/name/type/namespace,
  boolean system, explicit nullable parentAppId, and the number of
  childApps rows *returned in that response*. Do not claim that the
  returned page is the complete child inventory.
- Reject missing, mismatched, boolean or malformed identifiers and failed
  responses. Omit unsupported or unsafe optional fields. Never retain raw
  configuration, settings, page HTML, child labels, secret-looking values or
  arbitrary tool text in public receipts.
- Mark such a record as typed_app_class_identity, enabling the existing
  source-coverage contract to distinguish verified **reported instance
  identity** from still-unverified **independent native class binding**.
- Explicitly set nativeClassBindingVerified=false. Neither an app's
  self-reported type name, namespace=hubitat, system=true,
  parentAppId=null, nor child app count establishes an authoritative
  built-in Rule Machine parent relationship.
- No new MCP/tool calls, model rounds, permissions, automations, rule writes
  or claim of native Rule Machine authoring capability. The writer continues
  to fail closed without a separately verified native class contract.

## Acceptance and limitations

CI tests check exact target matching, missing or untrusted metadata, bounded
projection, and distinction between verified instance identity and unverified
native binding. A new **installed** read-only answer/Technical JSON is required
after release to verify actual source-data shape and publication. If the MCP
server omits appTypeId, no typed instance receipt can be produced and the
existing evidence requirement correctly stays unverified.

The user's source provenance reports
model_delivery_verified=false, first_attempt_verified=false, and
deployed_build_sha_verified=false, so neither first-answer quality
certification nor deployed build-SHA attestation is claimed.
