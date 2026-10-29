# HomeBrainOS v0.18.204 — Verified investigation focus and synthesis efficiency

## Live reproduction

The 29 October v0.18.203 Native V2 trial returned a source-attested Google Nest Hub (device 7934) snapshot, the device's 06:01:28.979 generic excessive-load WARN, and a device-produced volume=50 event with the same printed timestamp. However, focus_ids was empty because the tool-validated hub_get_device path did not propagate the user-referenced device into the incident scope. As a result, the generic warning incident packet, multi-occurrence correlation and source-bound incident report were omitted. Unrelated hub events and other-device warnings dominated the final output. Total duration was 54.079 seconds, including 30.759 seconds in a model-only synthesis which could not publish independently verified causal conclusions.

## Fix

- Introduce a general, read-only evidence-derived device focus anchor. After a successful, host-validated hub_get_device READ, require matching requested and returned device ID, existing verified device identity, and an explicitly user-referenced whole numeric ID or exact multiword returned device label (with a conservative displayed-name alias). Then add to focus_ids with an auditable verified_focus_receipts read/basis. Other device reads and broad hub questions remain unfocused. No keyword-based request routing or automatic MCP calls.
- Carry the verified focus through warning attribution, source coverage, device history, structured claim catalog and cross-occurrence correlation. The model remains free to choose tools, while the host rejects unscoped history proposals for a uniquely verified target.
- Skip expensive final model-only synthesis when independently observed generic warning and scoped device events already support the source-authoritative incident report. Preserve synthesis for other investigations. The root cause, driver method and CPU attribution remain unverified.
- Add focused unit and full agent replay regression tests: positive verified ID and name anchoring, no focus from unrelated hub audits or identity mismatch, incident timeline matching and irrelevant warning filtering, and no discarded model-only synthesis.

## Limits and acceptance

The latest bounded warning sample contains a single 06:01:28.979 warning and volume=50 observation. Older incidents from separate investigations do not become part of this sample without newly retrieved source records. Time coincidence is not causation. V2 remains experimental and strictly read-only; production Main Ask and Hubitat devices/rules are unchanged. Full repository CI is required before merge; live behaviour must then be checked by rerunning V2.
