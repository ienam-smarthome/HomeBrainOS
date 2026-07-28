# Hubitat MCP AI 0.10.216

- Prioritizes explicit driver health evidence (`healthStatus`,
  `networkStatus`, and `rtt`) over last-activity age.
- Treats offline/unavailable health states and ping timeouts as explicit
  offline evidence.
- Allows non-sensitive Ping and Refresh commands for ambiguous
  HealthCheck-capable devices, limited to five active checks per request.
- Keeps stale classification separate: inactivity alone does not prove a
  device is offline.
