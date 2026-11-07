# HomeBrainOS v0.18.454 — Dual-axis memory + CPU chart and clearer diagnostic inspection

## Charts

- Unified incident timeline now defaults to one **combined memory/CPU overlay**:
  blue external free OS memory against the independent left MB scale and green
  native five-minute CPU load *equivalent* against the independent right %
  scale. This percentage derives from native load and configured core count;
  it is not a measured CPU utilisation percentage.
- The original vertically separated, time-aligned memory and CPU panels are
  still available from the layout switch. Switching views only redraws local
  saved observations; it does not issue new Hubitat requests.
- Both layouts have dotted inspection guides for each real source reading.
  Detail metric charts are taller, with dotted time and value guides, better
  hover-tooltip positioning, responsive axis tick density, and marked actual
  minimum/maximum samples.
- Source timestamps are preserved. Downsampled real extrema and boundaries,
  missing-interval breaks, confirmed Hubitat systemStart events and external
  connection incidents stay distinct. Chart alignment does not establish
  the cause of a memory drop or reboot.

## Operational scope

Browser presentation only; no change to recorder polling, SQLite history
retention, external probe URLs, Hubitat/HA hub settings, automations, device
controls or authorisation gates. Node-backed synthetic tests exercise actual
overlay rendering, source-distinct paths, dual scales, point readout, preserved
memory gap and local switch back to aligned panels. Live installed UI visual
validation is still required after installing this version.
