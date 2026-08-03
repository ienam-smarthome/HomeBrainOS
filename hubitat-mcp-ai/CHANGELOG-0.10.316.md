# 0.10.316

- Added a fixed request-outcome presentation contract for `success`, `unresolved`, `refused`, `cancelled`, and `failed`.
- Added stable normalized values, human-readable labels, and tone tokens for future WebUI outcome styling without duplicating classification policy in browser code.
- Preserved the existing `metric_rows` response format and privacy-safe fixed metric vocabulary.
- Added exhaustive tests for supported outcomes, normalization, unknown-value rejection, and backward compatibility.
