# 0.16.165 — Correct device ID lookup and qualify stale-rule investigation

- Numeric device references such as FP2 parent 7334 in `homebrain_resolve_device(name='7334')` now issue `hub_get_device(deviceId='7334')` instead of incorrectly searching `hub_list_devices(labelFilter='7334')`.
- A failed, unauthorized or mismatched numeric-ID read is reported as **unverified**, never proof that the device was deleted or is absent. Authoritative health attributes are returned with verified device details.
- Improve the model's read-only Rule Machine investigation evidence policy: distinguish configured IF conditions, triggers and required expressions; separate possible retained sensor-state risk from proof of historical execution.
- Explicitly treat old activity timestamps as observational, not automatic disconnection evidence; follow parentDeviceId metadata when available and do not infer historical FP2 input values from current offline status.
- Warn that adding a motion trigger alone does not fix an offline lux dependency. Safe recommendations must be supported by the platform's automation capabilities.
- Regression tests cover direct ID lookup, inaccessible and mismatched-ID replies, transport failures, and automation analysis grounding.

Read-only. Does not change Rule Machine apps or device states. This corrects the local numeric-ID resolver and AI prompt policy; direct arbitrary MCP calls that bypass the resolver remain governed by the MCP tool contract.