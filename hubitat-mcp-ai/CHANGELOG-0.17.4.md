# 0.17.4 — Read the configured sensor before saying the trigger is unknown

HomeBrain 0.17.3 correctly explained the light's `setLevel(50)` command and named its producing app, but the follow-up stopped after reading app configuration and native logs. In the 07:53 Bathroom Light 1 case, the answer explicitly named **LWR01 Bathroom Occupancy** as the configured input without requesting that device's event history.

## Causal evidence completeness

- Do not gate configured-sensor investigation on the target light's cached identity having a room. The already-read authoritative history may supply the room, and exact configured device references remain eligible even when room metadata is unavailable.
- Recognize configured sensor attributes from compact and detailed identity forms (motion, occupancy, presence and explicitly configured contact), including `OccupancySensor` capabilities and advertised attribute lists.
- If the specifically configured sensor lacks attribute metadata, make at most two read-only, name/configuration-grounded attribute probes. A probe alone is never evidence that an attribute changed.
- Compare only observed, correctly timestamped active sensor events close to the light's ON transition. A post-transition report remains unverified as an upstream cause.
- Retain the short ordinary-language answer. Record any actual sensor-boundary match in request evidence, including sensor name, event time and signed event-to-light delta.
- Never attribute activity to unrelated unconfigured or mismatched-room sensors.

## Tests

- The configured LWR01 sensor is still selected when the identity lacks room and capabilities.
- Occupancy-specific capability and explicitly configured contact events.
- Same-room safety and time-alignment constraints.
- End-to-end agent regression: the target light identity omits its room; app configuration names the input; its matching sensor history is fetched and cited in receipts before concluding.
