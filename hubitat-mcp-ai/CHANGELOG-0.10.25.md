# 0.10.25

- Adds a central typed `EntityResolver` contract around the shared selected-device
  graph, including match reasons, confidence and action-capability evidence.
- Performs capability-aware plan validation before commands or ambiguity choices.
- Reports command outcomes as completed, sent, failed or uncertain, while retaining
  existing `success`, `submitted` and `verified` compatibility fields.
- Adds the three public route classes `fast-control`, `fast-read` and `agent` plus
  regression scenarios for ordinal resolution, unsupported actions and delayed
  device-state verification.
