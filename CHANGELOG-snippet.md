## v0.9.2-alpha - Device Inspector & Actionable Housekeeping

Added Device Inspector to make housekeeping counts actionable. HomeBrain can now list unknown switch-state devices, unassigned room devices, duplicate names, generic devices, and devices with weak capability data. Added `/api/device-inspector` and natural-language support for questions like “what are the unknowns?”.

## v0.9.1-alpha - Performance Baseline & Tomorrow Review Pack

- Added persistent performance snapshots so HomeBrain can compare load over time.
- Added actual Maker API GET counters, error counters and last-call timing.
- Added `/api/performance-baseline`, `/api/performance-compare`, and `/api/performance-snapshots`.
- Added assistant prompts for "save performance baseline" and "compare performance".
- Saved startup and scheduled performance snapshots for next-day CPU review.
