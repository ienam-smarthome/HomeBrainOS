# v0.18.337 — verified driver-source code identity before MCP reads

## Live evidence (v0.18.336)
The user supplied one read-only Gemma 4 Ollama Cloud device-telemetry investigation: 21.232 s end-to-end, 5 provider rounds (17.553 s provider time) and 6 recorded calls. Compared with v0.18.335's 24.910 s, 5 rounds and 8 calls, the later run used two fewer tool calls and completed 3.678 s sooner. Different execution windows and source history mean **no controlled performance gain is proven**. The `single_device_broad_reads_suppressed` counter did not appear; absent broad calls do not prove this guard itself fired.

The model issued a failed `hub_get_source(type=driver,id=7103)` after reading target device 7103's state and history. It confused the **device-instance ID** with an unverified **driver code ID**. The bounded result contains no verified installed driver source link or method interpretation. `mqttStatus=connected` and `healthStatus=offline` remain reported driver attributes, not independent physical connectivity proof.

## Architectural fix (source namespace, not case wording)
- Add `driver_source_identity_guard.py` and apply it at the **existing read-only MCP execution gate**, after target identity/history receipts and before the source API call.
- For a single positively resolved telemetry target, `hub_get_source(type=driver)` must use a source-code ID **explicitly linked** to that target by successful, device-scoped metadata. A device ID, unrelated app/driver metadata or an arbitrary numeric identifier does not qualify. Unknown mapping is reported as an unverified evidence gap; no guessed source call is issued.
- A verified source-code ID from targeted `hub_get_device` or `hub_list_devices` metadata remains usable. Other target reads, app source investigations, device logs, comparative/lighting/heating and all mutation permissions are unchanged.
- Register only a fixed non-identifying blocked-read counter. No new model round, network read, physical test, credential handling or hub mutation is introduced by the check.

## Validation and limitations
Source tests check correct/incorrect ID namespaces, unrelated and falsely linked source objects, positively linked code ID, missing history/state, multi-target fail-open, and cross-domain noninterference. All existing full-suite/CI and offline quality gates are required. The official answer-quality scorecard remains **NOT MEASURED**. A successful source download would still need method-by-method trace and independent broker/device evidence for root-cause claims.

**Important remaining architecture:** The published v0.18.336 answer is still model-replaced (`replacementPerformed=true`; `incomingVerifiedRawModelDraft=false`). Preventing invalid driver IDs does not make arbitrary model prose source-attested or fix the five-round reasoning pipeline. Next Q3 milestone: instrument authenticated model draft provenance and claim-based source validation across telemetry, lighting and heating before enabling model-first publication.

## Rollback
Revert the driver source read-admission module, its orchestrator call and version bump. Device command permissions and causal evidence limits are not modified.
