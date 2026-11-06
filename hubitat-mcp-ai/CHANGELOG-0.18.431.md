# HomeBrainOS v0.18.431 — bounded incident evidence drill-down

- Add **Investigate** next to each unified-timeline event, and **Investigate selected time** for graph cursor observations.
- An on-demand read-only **Incident investigation** view offers ±5, 15, 30 or 60 minutes around an offset-aware UTC focus; the default is ±15 minutes. Results use the installed recorder retention window.
- Show exact recorded OS-memory minimum, native five-minute CPU-load equivalent maximum, native free Java minimum, last successful external probe before and first after the focus, retained sample counts and gaps. Confirmed Hubitat systemStart and external connectivity episodes are separate source-backed events, not assigned causes.
- Integrate the existing Historical Evidence Journal using bounded device-event previews, grouped per-app log receipt counts without app-log bodies, and journal connection gaps. Empty/expired/truncated windows explicitly remain incomplete.
- Add Copy evidence summary and Source JSON; no extra polling, live Hubitat requests, scheduled tasks, write calls, AI model inference or automatic causal conclusions.
- Preserve full timeline, range selector, standalone detailed graphs, System Check, Ask/Speak and Rule Machine operations.
- Regression-test API validation, source clock semantics, real event sequence, bounded response, app-log privacy, source expiry, and no Hubitat mutations.
