# HomeBrain v0.17.61 — Ollama empty-assistant response recovery

## Provider resilience

- Treat a native Ollama response as empty if it contains neither assistant
  answer text nor native tool calls, including valid JSON whose message
  only contains `thinking`.
- Recover a completed empty Ollama model round **once** by retrying the same
  prepared messages and declared tool schemas with streaming disabled.
  Set `think: false` for supported reasoning model families so a
  thinking-only generation can produce final answer text instead.
- Do not retry network timeouts, provider status failures, invalid JSON,
  cancellations, or already successful tool-call rounds. The model transport
  does not execute MCP tools. All command/automation confirmations remain
  under the existing action policy.
- If the recovery also contains no usable assistant message, keep an explicit
  provider error, now saying that the single non-streamed retry failed.
- Add privacy-safe request counters for attempted and unsuccessful
  empty-message recoveries. Provider thinking traces remain excluded from
  logs, agent conversations and API answers.
- Add streaming/post regression tests including a normal successful stream
  that must not trigger the retry, and preservation of declared tools.

## Evidence clarification

- Extend bounded, command-only telemetry prose reconciliation to cover
  claims of "no incoming telemetry updates" and asserted contradictions
  between stored `mqttStatus` and health attributes. No recorded state
  event is different from verified physical transport silence.

## Limitations

A model response can be empty for several reasons, including provider-side
generation behavior or interruption. This release does not assert one root
cause for the photographed v0.17.60 incident and does not fabricate an
investigation result if both model attempts fail. Live validation is required.

The add-on's `general_task_engine_enabled` remains opt-in. No Hubitat
device, rule, switch or automation setting is changed.
