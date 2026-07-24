# Hubitat MCP AI 0.10.75

- Replaces the generic **Available** label in the all-device inventory with a
  deterministic primary live state such as On, Open, Active, Locked, Heating,
  temperature, humidity, power, battery or health.
- Normalizes dictionary and list-shaped Hubitat compact states without issuing
  a separate detail request for every device.
- Shows **State unavailable** when the compact inventory genuinely contains no
  recognized live state, and keeps disabled devices clearly marked.
