# Hubitat MCP AI 0.10.160

## Changed

- Added `AskCompositionBuilder` to capture compatibility installers behind the
  typed request-layer model introduced in 0.10.158.
- Converted all ten auxiliary request wrappers in `entrypoint.py` to named,
  ordered captures followed by one verified finalization.
- Preserved every installer result, route registration, controller patch and
  final cancellable-request endpoint.
- Kept climate evidence, firmware retry, rule-disable and entity-resolution
  service installers as direct calls because they do not mutate the request
  handler.

## Validation

- Exact auxiliary outer-to-inner ordering and installer-result tests.
- Untracked mutation and missing-wrapper failure tests.
- Real entrypoint startup composition smoke test.
- Focused auxiliary routing and presentation regression suites.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
