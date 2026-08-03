# 0.10.317

- Added privacy-safe `outcome_presentation` metadata to `/api/ask` and `/api/chat` responses.
- Exposes only the fixed normalized outcome value, human-readable label, and tone token.
- Preserved existing response fields and returns `null` for legacy outcomes without metrics.
- Added focused serialization coverage for all five supported outcomes.
