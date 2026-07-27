# Hubitat MCP AI 0.10.177

## Fixed

- Fixed add-on startup after the runtime route bridge stopped wrapping
  `application.ask`.
- Finalizes the declared request stack before rebinding the HTTP routes.
- Runs the runtime bridge directly instead of incorrectly capturing it as an ask
  wrapper.

## Safety

- The composed request-handler order is unchanged.
- Runtime diagnostics, Web UI routes, cancellation and all guard and terminal
  route behaviour remain unchanged.

## Validation

- Added a startup wiring regression that rejects recapturing the non-wrapping
  runtime bridge.
- Existing request composition and blocking release validation remain required.
