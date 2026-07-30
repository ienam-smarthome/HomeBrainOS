# Hubitat MCP AI 0.10.244

## Capability-driven live reads and speech-friendly comparisons

- Makes the safe high-level local read tools available to every live-read
  request, allowing the model to select capabilities without phrase-specific
  exposure rules.
- Keeps the authoritative local Hub Info snapshot in place of the generic
  remote Hub Info tool for live-read requests.
- Replaces symbolic comparison operators in deterministic answers with natural
  language such as “at or below,” “above,” and “not equal to.”
- Ensures browser speech reads battery, temperature, humidity, and other sensor
  thresholds without dropping comparison meaning.
- Adds regression coverage for paraphrased whole-home requests and every
  deterministic comparison operator.
