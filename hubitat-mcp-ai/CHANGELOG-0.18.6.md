# 0.18.6 — Model-led Groovy source investigation

**Architectural change:** The source-code inquiry no longer returns immediately from a deterministic host function with model:null. Instead, the normal Gemma/DeepSeek agent owns tool choice and evidence synthesis.

- Registers `homebrain_read_groovy_source` as an AI-selectable, bounded read-only evidence tool. It is exposed for explicit installed-app source investigations, but never synthesizes a root-cause answer itself.
- Keeps the rule/config/status snapshot routes for appropriate narrow questions; Groovy implementation questions bypass those shortcuts.
- Instructs the agent to verify installed app versus code identity, explore live advertised MCP readers, interpret retrieved snippets, challenge unsupported inferences, and report incomplete source coverage.
- Avoids causal device/command-history coverage requirements for source-focused questions. The source investigation goal concerns code access and semantics, not historical button event producers.
- Fixes a concrete v0.18.5 bug: `hub_read_apps_code` is a gateway/container, not by itself a raw-source operation. It must not be called with a bare `{"appId":"4019"}` as a source reader.
- Maintains strict read-only effect classification and existing paid model authorisation/budget. No writes, no hard-coded code ID 1453 or baked-in lockout conclusions.
- Regression tests cover code-vs-config routing, model-visible tools, direct source leaf selection and evidence-only outputs.

**Limitations:** The connected MCP server's actual source-reader operation and argument contract must still be verified through a live test. Successful source retrieval is not implied by passing CI. Source completeness and method behaviour must be stated as unverified unless actual source text is returned.
