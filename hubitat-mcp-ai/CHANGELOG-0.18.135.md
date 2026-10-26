# HomeBrainOS 0.18.135 — prevent wasted AI retries and validate historical samples

- Take two independently fetched incident-history pages (150 then 500) through the existing verified, read-only ToolExecutor gates. Compare typed, in-window event fingerprints; inconsistent source snapshots are flagged, never converted to claims that commands were physically or historically absent. No cross-run persistent tracking or added Hubitat writes.
- Record bounded reasons when source rows are excluded by the V2 evidence projection; never leak raw rejected content. This can distinguish unreturned events from unsupported/invalid source representations.
- When a verified historical issuer ID is missing from the app list, optionally retrieve its current app configuration if the live MCP gateway schema supports it. Only one host-approved, read-only and evidence-derived issuer query is added; current settings are **not** historical execution proof.
- The opt-in V2 AI planning budget is now 60 seconds (from 40), within the existing overall bounded experiment deadline. Planning failures use deterministic source-backed synthesis and skip extra AI atomic-selection/repair calls, avoiding long, misleading post-timeout model work.
- Production V1 and all mutation permissions remain unchanged. Real-world Hubitat completeness and model speed still require live comparison.
