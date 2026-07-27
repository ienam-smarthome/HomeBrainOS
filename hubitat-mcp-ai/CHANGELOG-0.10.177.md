# Hubitat MCP AI 0.10.177

## Fixed

- Fixed the add-on startup crash introduced when `runtime_route_bridge` stopped wrapping `application.ask` but was still captured as an ask-layer installer.
- Finalises the request composition first, then performs HTTP route rebinding directly.
- Preserves the composed request handler, cancellable `/api/ask`, runtime diagnostics, Web UI routes and shutdown cancellation.

## Validation

- Added a focused regression asserting that runtime route setup occurs after request composition finalisation and is not captured as an ask layer.
