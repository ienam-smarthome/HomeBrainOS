# Hubitat MCP AI 0.10.453

## General evidence reasoning

This release changes HomeBrain's model-driven read loop from question-specific reasoning exceptions toward one general evidence-review contract.

- Reasoning-capable Ollama model families now receive native `think=true`; provider reasoning traces are discarded and never stored in HomeBrain conversation, evidence, logs, or API responses.
- Every model-driven tool result carries a generic evidence-review instruction: re-read the whole request, check whether every material part is supported, gather more evidence only when materially needed, synthesize rather than dump raw fields, and distinguish observation/calculation from inference.
- Native multi-tool rounds can no longer be cut off by the first deterministic presenter result. When a model deliberately emits several calls in one round, HomeBrain lets the complete round execute before synthesis. Single-tool requests keep the existing deterministic fast presentation.
- Control ambiguities still fail into deterministic clarification instead of being hidden inside model synthesis.
- Final no-more-tools synthesis uses the same general evidence contract and explicitly prohibits presenting correlation as proven causation or exposing hidden reasoning.
- No new user-question regex, phrase handler, or domain-specific intent route is introduced by this release.

## Validation target

Regression coverage proves that a two-tool round containing a normally short-circuiting deterministic tool executes both calls before a second synthesis round, while a one-tool request still completes in one provider round. Transport tests verify native thinking is enabled only for supported model families and that provider `thinking` content is removed before the assistant message reaches HomeBrain.
