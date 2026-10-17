# 0.18.23 — Recover live device history and logs after MCP gateway mismatches

## Live finding

The v0.18.22 strict-paid DeepSeek investigation retrieved the full Groovy source of Bedroom 3 Mesh driver code 3686, projected relevant methods, and retrieved current device state. It failed to retrieve scoped device history and logs: two gateway compatibility rejections were followed by duplicate-call suppression. The final answer correctly marked its source+runtime correlation unresolved; provider time was approximately 126 seconds. This release addresses the *tool-routing* failure, not the physical device's unknown root cause.

## Architecture changes

- Prefer explicit live MCP tool-schema operation enums over older/prose gateway operation descriptions. A gateway advertising a named operation in its schema must not be rejected because its descriptive text omits the operation.
- For a failed read-gateway sub-operation, ask the request-scoped tool catalog for exactly **one** positively advertised compatible read gateway, grounded in the live gateway schema or structured exact operation discovery. If unique and permitted, transparently execute the same arguments through that gateway. Do not guess from operation names or fuzzy model text.
- A gateway call rejected before execution is not a completed read. Remove its signature from the duplicate-call set so an informed later retry can succeed following tool discovery.
- Preserve original model tool-call identity in the conversation while reporting the verified actual gateway used. Record `gateway_read_rerouted` for audits.
- Gate corrections to `hub_read_*` only and re-evaluate tool effects. Mutating, ambiguous, undeclared and incompatible mappings never silently upgrade to permissions.

## Verification and limits

New tests cover mismapped `hub_list_device_events` and `hub_get_logs`, explicit schema enums overriding incomplete descriptions, structured discovery, nested gateway arguments, ambiguity, wrong mappings, and no management/write gateway upgrade. This change does **not** infer that any physical MQTT packet, Tasmota reply or root cause was verified. If scoped event history or logs remain unavailable, investigation status must remain unresolved.

All three GitHub CI workflows must pass before merge; subsequent live installation and retest remain necessary.
