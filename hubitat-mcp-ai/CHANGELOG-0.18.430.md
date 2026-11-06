# HomeBrainOS 0.18.430 — unified Hub Diagnostics incident timeline

- Add a **Unified incident timeline** inside the existing expandable external Hub Diagnostics section. The range selector remains shared with the detailed metric chart (1h–30d).
- Use a single aligned local-SQLite timeline response with externally sampled free OS memory, distinct native five-minute CPU load-equivalent readings, confirmed Hubitat systemStart records and externally measured connectivity-loss intervals. Two separate y-scales share one time axis.
- Preserve actual minimum and maximum observations and gap boundaries for large windows. Never replace missing values with zero, draw interpolated bridges across gaps, or infer a restart cause from memory or CPU coincidence.
- Shade recorded probe-loss episodes and mark confirmed startup timestamps distinctly; the event list includes exact source times and recorded memory minimum/CPU maximum in the selected window.
- Include mouse/touch and keyboard inspection, a direct link to the read-only source JSON and a shortcut to the existing Historical Journal for manually correlating other evidence. The views do not claim an automatic app-log causal join.
- Add dedicated regression coverage of real timestamps, source freshness, loss recovery, empty coverage and no mutation/Hubitat polling.
- Keep the detailed metric chart, 30-day recorder retention, System Check, Historical Journal, basic dashboard and Ask/Speak unchanged. No extra Hubitat requests, controls, rule edits or hub reboot.
