# Hubitat MCP AI 0.10.186

## Shared monitored-power discovery

- `show power devices` now uses the same deterministic inventory and bounded
  `hub_get_device` fallback as whole-house power accounting.
- The dashboard monitored-power tile and direct current-power summary therefore
  use the same source of truth.
- Missing power attributes remain missing; genuine numeric 0 W values are shown
  as idle readings.
- Technical details expose whether targeted fallback discovery ran and which
  candidate diagnostics were produced.
- The historical `OctopusEnergySummary` export is restored as a compatibility
  alias to `OctopusLiveMeterSummary`.
