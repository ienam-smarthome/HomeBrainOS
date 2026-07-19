# Hubitat MCP AI changelog

## 0.4.41

- Keeps a validated semantic metric comparison on the deterministic MCP executor even when one evidence request shape fails.
- Starts with the known-compatible compact capability read carrying live `currentStates`, instead of making live evidence depend on optional detailed fields.
- Treats detailed attributes as optional enrichment and catches each MCP request-shape failure independently.
- Continues to compact no-space capability aliases such as `PowerMeter` when the canonical capability spelling is rejected or empty.
- Blocks Cloud fallback after a metric intent has been validated, so Cloud can no longer replace an MCP evidence error with an unsupported numeric claim.
- Shows a structured `Live comparison unavailable` result with the exact evidence failure in Technical details when no compatible MCP read succeeds.

## 0.4.40

- Fixes semantic comparisons returning zero readings when the MCP detailed catalogue exposes attribute definitions but keeps current values in compact `currentStates`.
- Merges detailed metadata with a fresh capability-filtered summary by Hubitat device ID before Python compares or ranks values.
- Retries compact no-space capability names such as `PowerMeter` for custom Hubitat drivers.
- Falls back to merged all-device detailed and summary evidence while still refusing to guess when no numeric live value exists.

## 0.4.39

- Replaces phrase-specific analytical read patches with a general semantic read-intent pipeline.
- Uses local `qwen3.5:4b` only to convert analytical read questions into a strict allowlisted JSON intent; the classifier has no MCP tools and cannot execute commands.
- Executes power, temperature, humidity, battery, illuminance and energy comparisons deterministically from Hubitat evidence.
- Supports highest, lowest and ranked results by device or room.
- Separates whole-home aggregate meters from individual-device rankings.
- Keeps exact controls and established fast shortcuts outside the semantic classifier.

## 0.4.38

- Marks Hubitat MCP AI as `stable`, removing the Experimental lifecycle badge.
- Keeps the Supervisor-facing release version in plain numeric form.
- Documents Supervisor/store reload recovery when Home Assistant caches an older `version_latest` value.

## 0.4.37

- Adds a visible `Refresh Hubitat devices` action in the web interface.
- Clears shared Hubitat device-read caches before rebuilding selected-device membership, detailed metadata and dashboard counters.
- Centralises release metadata validation across the Supervisor manifest, backend, changelog and Cloud setup script.

## 0.4.36

- Uses a plain numeric add-on version for Home Assistant Supervisor compatibility.
- Separates the add-on lifecycle stage from the version string.

## 0.4.35-alpha

- Replaces the hard-coded rain-bearing weather condition icon with condition-aware icons.
- Keeps rain, showers, thunder, snow and fog icons only for matching conditions.

## 0.4.34-alpha

- Republishes the suffix-safe multi-device control release under a fresh version to test Supervisor repository detection.

## 0.4.33-alpha

- Resolves spoken base names such as `fan switch` to a uniquely selected label such as `Fan Switch (Tuya Local)`.
- Keeps multi-device control all-or-nothing and blocks duplicate suffix-free labels safely.

## 0.4.32-alpha

- Routes explicit named conjunctions through deterministic MCP control.
- Requires every requested target to resolve uniquely before any command is sent.
- Verifies final states with fresh Hubitat reads and never lets AI-only text claim control success.

Earlier release history remains available in the repository commit history.
