# HomeBrainOS 0.16.134 — Scheduler ownership and handler evidence

## Improvements
- Broad whole-hub optimisation reviews now interpret the full structured `hub_get_jobs` response **before** the ordinary 7,500-character source-packet limit truncates it.
- When available, show actual scheduled job entry counts grouped by **explicit owning app/device ID** and handler/method. Also show top handler names such as `sessionTick` or `autoPoll`, where the source provides them.
- Preserve the reported total, number of rows actually examined, unidentified owners and unknown method counts. Partial job result sets are labelled incomplete. When IDs are missing, report that ownership cannot be ranked rather than guessing from display names.
- Shared next-run timestamps are labelled as queued alignment only: they do not prove simultaneous execution, 24-hour invocation rates, contention, or CPU savings.
- The model receives a compact host-derived scheduler summary, not only an arbitrary first-page excerpt from a truncated 253-row job payload.
- Pure unit tests verify complete and partial 253-job cases, missing identities, alternate structured gateway shapes and no-fabrication rules.

## Limitations and safety
- No Hubitat apps, devices, schedules or rule configurations were changed.
- The actual MCP `hub_get_jobs` response schema must still be verified on the live add-on. Unknown nested shapes fail closed with existing coverage warnings.
- Cost attribution, event-history completeness, action-dependency mapping, and before/after quantified savings remain open under issue #733.
