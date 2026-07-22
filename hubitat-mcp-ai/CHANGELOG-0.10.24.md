# 0.10.24

- Fixes light inventories so a generic Hubitat `Switch` state no longer makes
  sockets, appliances, cameras and other switches appear as lights.
- Adds deterministic aliases for `total lights on time` and
  `show lights on time for today`.
- Calculates today's combined and per-light on-time from authoritative Hubitat
  switch events without sending the request to AI.
