# HomeBrainOS v0.18.145 — Evidence-first V2 device investigations

The previous Bedroom 3 Mesh investigation (device 7103) stopped after two MCP
reads, retrieving only 13 repeated health states from the past 30 minutes,
while an independent reference traced older device activity, hub-side MQTT
connectivity and scheduled automation commands. V2 also proposed nonexistent
MCP tools and rendered an empty timeline with irrelevant light/bulb wording.

This release improves the **generic investigation pipeline**, not specific
device ID keywords or answer corrections:

- **Manifest-gated current context:** when a question has a single independently
  verified target and no explicit historical window, try a read-only
  `hub_get_device` source read before the AI's causal hypotheses. Preserve only
  allowlisted current values (e.g. switch, health, MQTT status and lastSeen).
  A current snapshot is NOT evidence of an event that occurred on its lastSeen
  date and is never converted into one.
- **Adaptive transition history:** when the read gateway actually advertises
  `hub_list_device_events`, attempt a bounded earlier history using the
  device's source-reported last-contact timestamp, if valid and no older than
  31 days. Where the device reports a switch, select switch transitions to
  avoid flooding the evidence window with repeated health watchdog events.
  The tool's advertised maximum limit is honoured when present; a read
  response is not evidence of full source coverage or physical reachability.
- **Bounded AI tool-selection repair:** when every proposed read fails the
  host's live permission/schema/identity gate, one further planning round can
  use a small host-produced rejection reason. This never permits the model
  to install, invoke or invent a tool.
- **Better reporting:** display current status distinctly from the event
  timeline, show representative recent health events when no commands/switch
  changes were returned, and use device-neutral physical-state language.

The existing V2 token gate, explicit opt-in, source sanitisation, verified-ID
scope, read-only executor and source coverage disclaimers remain in force.
The feature is wired only into the opt-in V2 browser test route; production
V1 and all Hubitat automations remain unchanged.

This is not complete causal-analysis parity with a specialist manual
investigation: if app logs, driver source or older retained events are
unavailable through a verified MCP read and typed evidence adapter, V2 must
still report the resulting gaps rather than invent a root cause.
