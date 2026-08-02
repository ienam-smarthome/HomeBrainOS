# Hubitat MCP AI 0.10.303

## Added

- Record expired pending confirmations through the fixed `confirmation_expired` request metric.
- Count expiries at the `ConfirmationStore` purge boundary rather than inferring them from response text.
- Add regression coverage for multiple expiries, successful consumption, cancellation, and calls outside a request context.

## Safety

- Expired actions remain removed before confirmation consumption.
- Cancellation and successful confirmation are not misclassified as expiry.
- Session identifiers and queued action details are not exposed as metric labels.
