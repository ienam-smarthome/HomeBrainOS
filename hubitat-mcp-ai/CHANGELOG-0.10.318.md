# 0.10.318

- Added a visible WebUI outcome badge for successful, unresolved, refused, cancelled, and failed requests.
- Consumed the fixed `outcome_presentation` API contract instead of reclassifying response text in JavaScript.
- Restricted badge styling to the fixed positive, warning, neutral, and critical tone vocabulary.
- Inserted outcome labels with DOM `textContent` and retained compatibility with legacy responses that omit outcome metadata.
- Added focused regression tests for the badge contract, tone classes, safe label insertion, legacy fallback, and structural confirmation gating.
