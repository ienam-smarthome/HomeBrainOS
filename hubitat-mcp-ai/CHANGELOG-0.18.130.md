# HomeBrainOS 0.18.130 — incident-first V2 test and readable forensic report

- Before any model proposal, explicitly dated investigations attempt an approved, scoped, read-only device event history for the first live-verified target ID. If the source page does not reach the requested start, one larger page is attempted within the overall read budget.
- Source projection now scans bounded returned rows **before** retaining target-period events; source-oldest/newest and incident-start-reached metadata distinguish missing coverage from absence of events.
- A separate, short V2 **investigation summary** has a chronological command-versus-state table, possible interaction between different controlling app IDs (never physical proof), unverified causes and decisive next checks. The full lossless atomic record-based output stays in a collapsed technical report.
- Incident scope, historical completeness and write permissions are still host-controlled. Normal HomeBrain V1 and Hubitat mutation paths are unchanged.
- Regression tests include UK DST boundaries, capped pages flooded by newer events, missing-coverage warnings, unknown producers, competing controllers, duplicate read budgets and operator UI visibility.

**Limitations:** An upstream hub that only supplies a capped recent page may still be unable to recover old events, even with larger limits. A returned command does not prove the bulb physically responded, nor do the tests prove live Claude-level investigative accuracy.
