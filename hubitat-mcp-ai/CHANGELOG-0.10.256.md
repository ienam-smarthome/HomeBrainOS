# Hubitat MCP AI 0.10.256

- Correct automation status precedence to `broken → paused → disabled → active → unknown`.
- Detect `(Paused)` and `*BROKEN*` markers in automation names when Hubitat still reports the item as active.
- Preserve separate `broken`, `paused`, and `disabled` flags in structured `automation_items` output.
- Add regression tests for conflicting state signals and corrected grouping.
