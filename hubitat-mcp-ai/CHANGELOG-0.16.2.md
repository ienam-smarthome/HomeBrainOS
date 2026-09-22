# Hubitat MCP AI 0.16.2

## Authoritative fallback for state-dependent semantic controls

A live 0.16.1 Hallway test showed the semantic capability fix working: HomeBrain
correctly resolved **Hallway dimmer** as brightness-capable. The request then
failed before mutation because the native `hub_get_device_attribute(level)`
read returned `value: null`.

That is a different condition from “not brightness-capable”: the device can
support `setLevel` while its native current-state endpoint has never reported
(or cannot currently report) a level value.

### Generic precondition reader

Relative brightness and relative thermostat changes now use one state-dependent
precondition strategy:

1. read the cheap native attribute endpoint first;
2. if it returns a numeric value, use it;
3. if it returns no value / `neverReported`, perform one fresh
   `hubitat://context` bulk live-context read;
4. find the same device by stable ID and read the required attribute there;
5. calculate the relative target only from one of those live sources.

Concurrent room controls naturally coalesce the fresh live-context fallback in
the MCP client rather than each triggering a separate bulk request.

### No stale-state guessing

HomeBrain still does **not** calculate a relative change from cached identity
state. If both authoritative sources lack the baseline, no command is sent.

Instead of:

> Failed: Hallway dimmer.

the request becomes **Needs input** and explains that an absolute brightness
level/setpoint is required.

### Better evidence

The trace now distinguishes:

- native attribute value returned;
- attribute has never reported;
- attribute read error;
- fresh live-context fallback succeeded;
- fresh live-context fallback also had no numeric value.

This avoids low-level messages such as:

`float() argument must be a string or a real number, not 'NoneType'`

when the meaningful condition is simply “current state unavailable”.

### Outcome semantics

Add `device_control_needs_input` as a fixed privacy-safe request metric.
Missing state needed to calculate a relative command maps to `needs_input`,
while actual command/verification failures continue to map to `failed`.

### Regression coverage

Tests cover:

- native level missing with fresh live-context fallback succeeding;
- correct relative target compilation and verified string wire payload;
- both live sources missing -> no mutation;
- missing baseline -> `needs_input`, not `failed`;
- user-facing absolute-level clarification;
- outcome precedence when a real control failure is also present.
