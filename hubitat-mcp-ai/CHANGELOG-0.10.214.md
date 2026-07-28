# Hubitat MCP AI 0.10.214

- Includes compact live device attributes in the device manifest so common
  switch, motion, presence, battery, climate, and weather reads do not require
  redundant MCP/LLM rounds.
- Requires update-status fields and versions to be reconciled before reporting
  that hub firmware or the MCP application is current.
- Allows up to 12 sensitive actions from one user request to be reviewed and
  confirmed as a single group, enabling normal room-level multi-device control.
- Keeps the confirmation boundary intact: no grouped action runs before the
  explicit confirmation.
- Aligns low-battery answers with the dashboard threshold of 20 percent or
  below, explicitly excluding devices at 30 or 35 percent.
