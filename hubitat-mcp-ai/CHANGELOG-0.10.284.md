# Hubitat MCP AI 0.10.284

## Added

- Added a deterministic `homebrain_device_history` tool for named-device
  history questions.
- Added bounded `hub_list_device_events` reads with optional attribute
  filtering, shared fuzzy-safe target resolution, and newest-first event
  normalisation.
- Added deterministic history presentation and authoritative nested evidence
  receipts.

## Safety

- Event transitions are never presented as proof of who or what caused them.
- History windows are limited to 168 hours and individual responses to 50
  events.
- Unresolved or ambiguous devices fail without issuing an event-history read.

## Tests

- Added regression coverage for exact upstream arguments, bounds, target
  resolution, empty histories, evidence metadata, and causal-language safety.
