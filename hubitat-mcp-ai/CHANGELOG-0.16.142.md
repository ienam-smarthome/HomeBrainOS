# HomeBrainOS v0.16.142 — Safe investigation timeout response hotfix

## Live regression
- A scheduled-job review on v0.16.141 returned `'ObservedAgentOutcome' object has no attribute 'route'` instead of a report or a safe timeout summary.
- Root cause: `safe_partial_outcome` assigns `route = "investigation-timeout"` to a slotted `ObservedAgentOutcome` whose base `AgentOutcome` never declared the route field. Existing timeout tests used a permissive `SimpleNamespace` fake, so CI missed the production failure.

## Fix
- Add a default `route` field to `AgentOutcome`, and carry `route` through `build_observed_agent_outcome`.
- Continue using the evidence-only timeout fallback for either the overall investigation deadline or bounded AI synthesis deadline; do not expose unverified model recommendations.
- Test real `ObservedAgentOutcome` in both timeout branches, verifying `/api/ask` serialization, retained successful read-only evidence, and explicit route preservation.

## Safety and limitations
- This release **does not increase** the investigation or synthesis timeout, and it does not establish why the live request timed out. Follow-up live technical details are needed.
- No changes to Hubitat devices, apps, rules or scheduled jobs.
- Live installation and verification pending.
