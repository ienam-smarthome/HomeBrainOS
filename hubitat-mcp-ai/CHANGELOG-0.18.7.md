# 0.18.7 — Adaptive investigation core

- Complex read-only investigations in multiple domains now take the model-driven planning and tool-selection path rather than a narrow status presenter. Simple status lookups and explicit device controls retain their existing routes.
- For evidence-heavy questions, activate the existing bounded task planner and give the model a live MCP read-only tool view. No write capability or confirmation bypass is introduced.
- After an unsuccessful or empty read, the investigator is prompted to consider one distinct, relevant authorised source rather than repeating the same failed call.
- Source-code objectives have their own evidence requirement. Configuration reads and empty source responses cannot count as retrieved implementation text. Full code coverage must be verified separately.
- Tests cover code inspection, unexpected light behaviour, energy monitoring, Zigbee telemetry, scheduler analysis, and control-path safety.
- Existing manual paid-model selection and budget limits are preserved.

This release is an architecture change, not verification that the live MCP server can return installed Groovy source. Runtime tests are still necessary.
