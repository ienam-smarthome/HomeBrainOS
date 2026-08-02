# Hubitat MCP AI 0.10.306

## Security

- Upgraded FastAPI from 0.115.12 to 0.139.2.
- Added an explicit Starlette 1.3.1 pin so the shipped image receives fixes for the advisories reported against Starlette 0.46.2.
- Added a blocking weekly and change-triggered `pip-audit` workflow for the exact Python requirements installed in the add-on image.
- Audit reports are retained as JSON artifacts even when the blocking check fails.

## Validation

- Added repository contracts that keep the audit pinned, targeted at the shipped requirements, artifact-producing, and blocking.
