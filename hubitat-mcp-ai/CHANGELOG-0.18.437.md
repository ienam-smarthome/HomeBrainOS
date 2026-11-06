# HomeBrainOS 0.18.437 — clearer diagnostic chart axes and grid

## Changed

- Apply tidy, rounded y-axis scales with additional labeled ticks to the synchronized
  OS-memory and native five-minute CPU charts, and to the standalone resource chart.
- Add consistent horizontal and vertical grid lines to both plots. X-axis tick
  count fits the displayed width (compact time labels on a single day, dates
  preserved for longer ranges), improving both desktop and narrow-screen use.
- Preserve original external probe and native source timestamps, original saved
  data, missing-interval segment breaks, independent scales, and read-only
  incident investigation controls. Grid/tick positions are visual references,
  not measurements or estimated data.

## Validation

- Added tests for both chart integrations, consistent evidence-gap handling,
  rounded scale bounds, desktop/phone tick density and multi-day time labels.
- CI results are recorded on the PR; a merge and live add-on upgrade must be
  verified separately. No live Hubitat/Home Assistant writes or diagnostic
  recorder configuration changes were performed.

## Rollback

Revert this UI/release-only PR if chart labels collide or the grids obscure
data on a supported device. The retained recorder measurements are unaffected.
