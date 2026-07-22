# 0.10.17

- Routes Octopus meter display requests directly to the deterministic reader after
  every model-driven wrapper has been installed.
- Supports actual Hubitat labels beginning `Octopus Meter` as well as the legacy
  `Octopus Live Meter Display` names.
- Retains detailed and per-device fallbacks when list responses omit live values.
