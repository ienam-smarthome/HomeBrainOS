# Hubitat MCP AI 0.10.175

## Changed

- Removed the final legacy thermostat re-wrap from `runtime_route_bridge.py`.
- Kept the cancellable `/api/ask` route bound to the already composed registry
  handler.
- Prevented duplicate thermostat evidence reads and duplicate summary correction.

## Preserved

- Runtime version diagnostics.
- Home-page rebinding and cache-control headers.
- Request cancellation on shutdown.
- All deterministic writes, confirmations, guards and terminal routes.

## Validation

- Focused runtime bridge wiring tests.
- Existing thermostat registry and cancellable-request tests.
- Repository validation, Python compilation and blocking release gate.
