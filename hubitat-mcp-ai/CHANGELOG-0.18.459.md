# HomeBrainOS v0.18.459 — Recoverable source discovery and multi-part temporal reasoning

## Changed

- Host-opted read-only history requests recover a rejected known attribute using bounded raw events on the same resolved device, with explicit requested-attribute mismatch and actual observed dimensions. Direct legacy calls still reject by default.
- Expose observed state analyses and preserve recovery metadata in evidence. Never silently choose another device or equate missing snapshot fields with missing past events.
- Allow semantic plans to request raw history discovery without guessing switch. Infer a unique supported operating-state signal from actual rows.
- Compute reported thermostat heating/idle intervals. Configured heat mode is not demand, and cooling/pending/custom states are not skipped to fabricate a pair.
- Autonomous multi-part temporal reads can continue related-device evidence instead of forcing final synthesis after the first interval. Keep finite resource, cancellation, identity and write safeguards.
- Refresh existing MCP skill workflow from supplied and upstream references; no new runtime module, provider/paid-route or device/automation change.

## Evidence and validation

The supplied installed v0.18.457 heating attempt made 14 calls but no successful history read, then published an unsupported-switch error. Claude's screenshot illustrates useful output, not independently verified source truth or model parity. The repair targets this generic lifecycle failure across history domains, not household labels.

Local compilation passed. Fictional service and scripted whole-agent tests cover opt-in raw recovery, a nine-minute reported heating interval, related radiator reads in one user request, sensor-dimension mismatch, failed reads and unsafe mixed-state arithmetic. These are execution contracts, not measured model intelligence. [PR #1522](https://github.com/ienam-smarthome/HomeBrainOS/pull/1522) passed all four required workflows on final exact head `c9610fb1dd91ddbb8c232a39e8e169895e2f70ed`: **6,805 Python tests**, two nonblocking warnings, container smoke, metadata/import map, Hubitat tests and scorecard integrity. Squash-merged as `97a2c88ea65dec9f5fde54604966e0c082187a95`. The initial CI run caught two regressions: an unregistered recovery metric and host flags interfering with model-call identity/evidence review. Both were corrected; final CI revalidated the original contracts. Installed v0.18.459 and matched Gemma/Claude acceptance remain pending.
