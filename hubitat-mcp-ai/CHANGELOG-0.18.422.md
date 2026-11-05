# HomeBrainOS 0.18.422 — Diagnostic chart values

- Add visible numeric vertical-axis ticks with units for external Free OS memory, native Java memory, heap-used %, native load and HTTP latency.
- Show minimum, maximum and latest *observed* reading for the selected metric, including latest observation time.
- Hover or touch the graph to inspect each actual sample. Show the source time for native five-minute readings, and allow left/right keyboard navigation.
- Highlight the selected sample with a crosshair and tooltip; show individual points for short windows.
- Keep existing 30-second external OS polling, five-minute native Java sampling, SQLite history, outage event rules and Hubitat workloads unchanged.
- Do not interpolate readings across gaps; hide fabricated point values. No hub API request is made when exploring the graph.