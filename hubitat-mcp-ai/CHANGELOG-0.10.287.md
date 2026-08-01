# Hubitat MCP AI 0.10.287

## Fixed

- Restored `homebrain_resolve_device` and `homebrain_device_history` to the
  fixed lean registry. Both tools were constructed locally but omitted from
  the catalog order, allowing a broad discovered gateway to bypass them.
- Kept `hub_list_device_events` discovery behind the deterministic history
  adapter instead of exposing the whole `hub_read_devices` gateway.
- Short names such as `tab s9` now use the shared bounded variants and can
  resolve prefixed, punctuated labels such as `Block Tab-S9-FE` before reading
  event history.

## Safety

- The fix is based on structured operation-to-wrapper ownership, not prompt
  keywords or a device-specific alias table.
- Event-history reads retain bounded windows, authoritative evidence receipts,
  and the rule that state events do not establish causation.

## Tests

- Added end-to-end registry, discovery-shadowing, shared-resolution, evidence,
  and read-classification coverage for shortened device-history requests.
