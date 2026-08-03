# Grounding policy factory

Production requests select `LiveEvidenceAuthority` through the request-local
factory exposed by `grounding_policy.py`.

The base orchestrator continues to construct `GroundingPolicy` normally. When no
factory is active, that constructor returns the built-in deterministic policy.
During one production request, `homebrain_agent.UnifiedMCPAgent` installs its
bound `_create_grounding_policy` method in a `ContextVar`; the constructor then
returns a `LiveEvidenceAuthority` tied to that request's `EvidenceRecorder` and
`RequestMetrics` instance.

The factory token is always reset in `finally`. This keeps concurrent requests,
direct base-agent callers, and tests isolated without replacing symbols in the
`mcp_agent_orchestrator` module.
