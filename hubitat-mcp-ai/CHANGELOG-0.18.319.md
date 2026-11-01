# HomeBrainOS v0.18.319 — Stage 8.4 historical temporal integrity

## Motivation
After Stage 8.3's first consented historical read, the local Journal returned several old device-switch reports whose **declared event times** were substantially earlier than their **collector receipt times**. The UI showed both timestamps, but did not explicitly identify the discrepancy or warn against treating the receipt as proof of recent device liveness.

## Implementation
- Deterministic post-query audit of the **already returned** bounded single-device event set; no extra journal read, Hubitat request, model inference, cloud usage or device command.
- Separate first/last source-declared timestamps from first/last collector receipt times.
- Flag events where the declared time is more than 24 hours earlier than the receipt, and show minimum/maximum **apparent** source-to-receipt separation in days.
- Detect adjacent collector receipt-order inversions in source timestamp order. Neither clock is automatically authenticated, and these comparisons are not proof of transport latency or physical chronology.
- Explicit warning: delayed archive receipt may reflect replay, delayed ingestion or inaccurate clocks, and **does not show the device was online at receipt**.
- Keep full history coverage, physical execution, causal attribution, provenance trust and production publication approval false. Journal gaps describe observed collector outages, not historical coverage certification.
- Mobile UI adds concise temporal-integrity diagnostics above the read-only timeline, with no private labels or raw message content.
- Tests are synthetic and cover old source events received much later, out-of-order receipts, missing device-side timestamps, empty archives and privacy restrictions.

## Scope
This update is only diagnostic interpretation of the existing Stage 8.3 local history. A Hubitat source event is not an authenticated device-origin packet, and a report of switch OFF cannot establish command success, power draw, precise network loss or a unique cause.

## Manual acceptance
Update to v0.18.319, open **Live Shadow · Historical Shadow**, enter device ID, tick local-journal consent and select **Inspect archived device events (30 days)**. Look for a **Temporal integrity** section and warning. Compare source-declared and receipt windows. No AI, device commands or source-code inspection are enabled by this test.

Rollback by reverting the PR to v0.18.318.