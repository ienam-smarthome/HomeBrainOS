# HomeBrainOS 0.16.133 — Consistent performance recommendations

## Fixed
- Additional final evidence check catches the actual v0.16.132 output suggesting removal of app IDs 2954 and 2597 from the MCP Rule Server. Failed reads for already-deleted IDs do not prove persisted internal dependencies; without a configuration read, the recommendation now asks to trace the caller and input parameters rather than modify server configuration.
- Correctly describes successful but empty source-scoped reads: the LG webOS TV log query for device 7486 succeeded and returned 0 rows in the 6-hour window. This is distinct from not having read logs, and does not disprove the measured ~3-second average execution duration.
- Removes repetitive unsupported “no diagnostic read” wording in that scoped diagnostic subsection and suggests a read-only driver/connectivity inspection.
- Regression tests use the exact observed v0.16.132 diagnostic text, verify no false rewrites of actual log error statements, and keep state unchanged without supporting evidence.

## Safety and scope
- Read-only conclusion/answer-quality changes; no app, device, rule, or hub settings changed.
- Authoritative grouping of all scheduled jobs by owning app/method, complete event-history coverage, and measured impact estimation are not yet implemented (issue #733).
