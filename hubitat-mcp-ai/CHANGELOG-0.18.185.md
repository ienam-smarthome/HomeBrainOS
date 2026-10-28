# HomeBrainOS v0.18.185 — Focused source evidence and useful fallback

## Live basis (28 October 2026)

- Bedroom 3 Mesh (7103) investigation took 26.799s; device identity,
  lastSeen, healthStatus, MQTT broker status, events and watchdog warnings
  were retrieved, but equivalent current-state snapshots were read repeatedly.
  The AI ranked physical power loss above Wi-Fi/firmware failure despite no
  independent power or router evidence. lastSeen and dataAgeSeconds were
  inconsistent and must not be combined into a definitive failure timestamp.
- Google Nest Hub (7934) investigation took 22.762s and succeeded at nine
  reads. Its source evidence contained 22 excessive hub-load warnings and
  16 long-running runQ warnings (representative duration 147,429ms).
  The model's final 8s synthesis timed out, and a generic source fallback
  led with unrelated Bedroom 3 Mesh warnings, failing the user's question.

## General native-agent improvements

- When a model-selected lookup uniquely attests a device identity, store it
  as a subject focus rather than treating all sampled log sources equally.
- The host retains full bounded evidence receipts for technical review while
  the model sees the selected target's WARN/ERROR groups first; unrelated
  background warnings are omitted from the focused model view, not from
  technical evidence. Hub-wide questions are unchanged.
- Collapse equivalent current-state device snapshots across differing read
  arguments using a canonical hash of source attributes. Never collapse
  event histories, logs or configuration on that basis. The model gets an
  explicit no-new-evidence signal instead of the same bulky attributes.
  Two redundant snapshots trigger a bounded stop and answer completion.
- Final synthesis receives a concise, target-specific source brief. If a
  model cannot finish, the host supplies an evidence-referenced target
  conclusion distinguishing reported device state, driver warnings and
  unverified physical/causal mechanisms.
- A reported offline device with stale data does not justify ranking power
  failure over Wi-Fi or MQTT. An online media device can still have severe
  runtime warnings; such warnings do not independently prove whole-hub
  causation.
- The verified device IDs appear in native diagnostics and resolved_devices
  rather than the misleading empty list seen after successful name lookup.

## Safeguards and remaining work

- All native tool calls remain sequential, host-validated and READ-only.
- No current-state attribute by itself proves physical operation.
- All log history is bounded, and a watchdog/driver health cycle is not a
  genuine device heartbeat.
- The model may still make unsupported causal assertions when it completes
  a normal answer. Full material-claim-to-evidence validation and feedback
  across device, app, automation, hub and cross-system domains remain needed.
- Physical connectivity tests, driver source inspection and latency grading
  must be measured in live acceptance, not inferred from synthetic tests.
- Production Main Ask and Hubitat automations are not changed.
