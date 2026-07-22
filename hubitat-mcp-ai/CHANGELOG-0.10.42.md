# Hubitat MCP AI 0.10.42

## Authoritative device measurements

- Fixed named-device power and energy questions returning a false missing-value response when Hubitat had exposed the measurement.
- Device detail reads now use the upstream `hub_get_device` operation, translated automatically through the `hub_read_devices` gateway when gateway mode is enabled.
- Added support for MCP responses that expose an attribute value through `currentState`.

## Natural period-energy questions

- Phrases such as `How much energy did we use yesterday?` now use the deterministic Octopus period reader instead of the general AI evidence route.
- Added exact regression coverage for the Freezer (MQTT) power question and the natural yesterday-energy question.
