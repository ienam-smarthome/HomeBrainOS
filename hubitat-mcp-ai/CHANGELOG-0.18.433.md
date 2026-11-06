# HomeBrainOS 0.18.433 — independently verified incident triggers

- Keep the existing read-only on-demand Hub Diagnostics AI investigation flow and the underlying causal verdict explicitly unverified.
- Classify time-bounded authenticated Hubitat `lowMemory`, `update` and `systemStart` records from successful typed MCP event receipts, not from AI prose, app-log receipt counts, or coincidental timestamps.
- A critically-low-memory reboot event followed by startup verifies the hub's **reported reboot trigger**, not the process that consumed memory. A firmware update followed by startup establishes a recorded update-associated sequence, not the cause of a preceding external memory minimum.
- Show the exact Hubitat event timestamps and firmware builds in a host-authored evidence summary, even when the model's unsupported causal draft is withheld.
- In Technical details expose `restart_trigger_status`, `restart_trigger_evidence`, and `underlying_memory_cause: unverified`. Distinguish failed app-log reads from verified absence of logs.
- Correct external-versus-native recorder labelling for OS memory, five-minute CPU load, and Java memory values. Do not infer an uninterrupted outage from the time between an alarm and startup.
- Add synthetic 5 November incident regression cases, failed/stale/untrusted receipt safeguards, and read-only API response tests. No new Hubitat polling or writes.
