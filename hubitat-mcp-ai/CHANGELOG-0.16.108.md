# Hubitat MCP AI 0.16.108

## Readable temporal-history presentation

- Improves duration/history answers with a concise leading result, compact Markdown interval table, and one short caveat paragraph when deterministic interval evidence is available.
- Keeps recorded interval start/end times and exact per-interval seconds visible without dumping raw JSON evidence.
- Explains a leading unmatched inactive event, such as an OFF row whose earlier ON edge has rolled out of Hubitat's retained history, without inventing the missing duration.
- Preserves the 0.16.107 retained-page completeness semantics and all existing unverified-event-stream safeguards.
- Adds regression coverage for the live Bathroom Light 1 four-interval presentation shape and for deterministic table derivation.
