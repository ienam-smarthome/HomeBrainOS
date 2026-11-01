# HomeBrainOS v0.18.317 — Stage 8.2 verified detailed read-only shadow

## Real-device input

Live Shadow v0.18.316 for device 7103 successfully located the target in a 207-device compact context, with matching total, no explicit truncation and `switch: off`. The upstream `idsComplete` marker was absent/unrecognised. Therefore the context is **provisional**: it cannot establish whole-inventory identity coverage, physical plug connectivity, last packet time or why the plug stopped responding. The compact context included no healthStatus or mqttStatus, which is missing **evidence**, not proof of those states.

## New optional phone test

A distinct **Compare verified detailed device states** control requires fresh user consent before each run. It calls only the established read-only `mcp.get_audit_devices(identity_only=False)` inventory pathway. This may read **multiple paginated Hubitat device inventory pages** (not just one target), and the user-facing response contains only bounded allowlisted attributes for the one numeric device ID requested. No model, cloud, command, app source, historical log read, persistence or production publisher call is involved.

The projection **fails closed** unless the existing inventory pathway supplies verified freshness and identity/total provenance (`source=fresh_projected_gateway`, `projection=full`, `complete=true`, unique numeric IDs, and matched device count). The pathway's detailed-manifest fallback is not promoted to verified evidence. Typed detailed attribute lists and summary currentStates maps can be extracted, with conflicting duplicate values omitted. Only well-bounded numeric fields and explicitly enumerated status strings are returned; private labels, names, other devices, IP/MAC, errors, tokens and logs are excluded.

## Remaining evidence limits

Even a successfully verified *inventory* is only a fresh **Hubitat-reported state snapshot**. It does NOT establish device-origin packet provenance, event history, timestamp authenticity, successful device command execution, or why an OFF event occurred. Read-only historical investigation and the redesigned production publisher are still DISABLED.

CI uses mocked Hubitat reads and covers privacy projection, no identity-metadata loophole, fallbacks, duplicate IDs, conflicting fields, explicit consent, cross-origin denial, exact target output, zero AI and no production module changes. No live-device reads are performed by GitHub CI.

**Manual acceptance:** Update to v0.18.317, enter 7103, authorise and choose **Compare verified detailed device states**. A blocked source should report its proof gap rather than invent a state. If any verified health and MQTT reports appear, they remain distinct from physical connectivity.