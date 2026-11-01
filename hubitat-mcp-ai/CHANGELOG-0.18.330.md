# v0.18.330 — Stage 9.5: cross-source temporal evidence in natural investigations

## Live motivation
The 1 November 2026 Hallway Light 1 / app 4012 investigation returned motion-inactive events at 15:43:46.781, 15:47:43.288, 15:51:27.183, and 15:58:01.507 UTC, each followed by an OFF command from app 4012 roughly 15.1 seconds later. The model nevertheless concluded there was probably a periodic keep-off heartbeat, citing a different bounded sensor history window that returned no motion events. This contradicted positive later cross-source observations and was not a verified timer explanation.

## Generic solution
- Build a canonical, bounded, **read-only** source-linked sensor-to-command timing projection across episodes. Eligible inputs require explicit motion/presence/occupancy inactivity reports with the app recorded as a notified listener; eligible commands require an authoritative command-off event with app issuer provenance and a concrete target-device ID.
- Normalize offset-aware source timestamps to UTC, reject naive/unparsable clocks, deduplicate overlapping returned pages and boundary rows, and require at least **three separated commands** with consistent nonnegative lag from the same sensor to the same issuing app and target device.
- Expose compact observed command/input pairs, repeat count, median/range of source timing, target/app/source identity, and strict flags `causalDecisionVerified=false`, `physicalExecutionVerified=false`, `historicalCoverageComplete=false`.
- Send this projection into the existing natural-language final model synthesis **before** asking for its conclusion. Do not change model choice or grant new source/tool permissions.
- Preserve the identical structured projection in `investigation_coverage.crossSourceTemporalEvidence`; the final publication includes an observation-only correction if the model silently discards the pattern. A recurring timing match must never become a verified root cause, app timer expiry, or physical actuation.
- Do not mix a later positive pattern with the specific 15:29:23 command when its historical sensor record is missing. Empty pages are bounded, not evidence of absence.

## Scope and safety
- No new Hubitat, HA, diagnostics, local/cloud AI or physical device requests.
- No app-specific, room-specific or hardcoded sensor IDs in production logic. Only typed received tool evidence is used.
- No app source code, raw diagnostics, passwords, tokens or arbitrary private tool text copied into the output.
- Synthetic tests reconstruct the supplied four source-timed episodes and include missing listener identity, wrong command producer, invalid clocks, missing target ID, duplicate histories and target-event separation.

## Phone acceptance
Update Hubitat MCP AI to v0.18.330. In Free · Gemma, ask a fresh read-only investigation that retrieves an actuator's recorded OFF commands and its configured motion/presence sensor event histories within overlapping bounded windows. If three or more source-linked episodes remain available, confirm that the natural-language explanation and `investigation_coverage.crossSourceTemporalEvidence` both retain the pattern, without claiming a definite trigger for a separate unsupported focal command. If events have aged out, report that absence rather than inventing a conclusion.

Rollback: revert this PR to v0.18.329.
