# HomeBrainOS v0.18.67 — Correct upstream detailed-device capability shape

## Why v0.18.66 needed one integration correction
After v0.18.66 added a genuine deterministic confirmation path for the active night-idle TEST rule, upstream `kingpanther13/Hubitat-local-MCP-server` code inspection established that `hub_get_device(mode="details")` returns `{id, label, mode, sections: {attributes: {capabilities: [...]}}}`, not a root-level `capabilities` list. The original compiler checked root-level capabilities and would incorrectly return 'no usable capability list' despite healthy FP400 and Hue light devices.

## Fix
- Pass `sections=["attributes"]` to `hub_read_devices/hub_get_device` so the MCP server emits only the required capability section rather than the entire expanded device response (which can paginate into `contentFormat="json-fragment"`).
- Extract explicit capability names from both native detailed `sections.attributes.capabilities` and older top-level list shapes. Never infer capabilities from label or device ID. Reject mismatched or unreadable sources.
- Update the end-to-end orchestrator fake to emit the actual upstream detailed-device response structure; preserve its assert of zero model calls, no mutation before confirmation, two verified devices, exact native action payload and duplicate handling.
- No Hubitat writes from these repository changes.

## Next live acceptance
The user can update the HA add-on to v0.18.67 and send the short explicit ACTIVE creation prompt. It should read a real Rule Machine inventory, both device capabilities and native subtype guide, then produce `confirmation_required=true` with one pending native `hub_set_rule` action; no rule exists until the user separately confirms. Readback/health and 4019 conflict must be checked after creation.
