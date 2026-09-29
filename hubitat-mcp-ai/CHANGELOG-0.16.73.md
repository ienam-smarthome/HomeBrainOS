# Hubitat MCP AI 0.16.73

## Performance language hardening

0.16.73 is a narrow deterministic-grounding release. It intentionally leaves the 0.16.72 request-local evidence packet, four-tool performance path, single final synthesis pass, and normally three-model-round architecture unchanged.

### Fixed

- Treats database wording such as **“well within healthy limits”** as an unsupported qualitative threshold unless current-turn evidence defines one.
- Rewrites generic **“Performance Bottlenecks”** headings to **“Performance Outliers”** and **“Blocking Device Execution (High Latency)”** to **“High-Latency Device Execution”**.
- Fail-closes scheduler wording such as **“Executing this many tasks ... creates CPU spikes ...”** when only job timing/alignment evidence is available.
- Blocks frequent-reporting claims that activity adds **constant background overhead** without measured causal evidence.
- Converts latency-to-timeout/reachability suggestions into investigation-first language that does not assert a network/driver mechanism.
- Collapses the exact repeated **“does not establish that it; this is a measured performance concern...”** sentence corruption exposed by the 0.16.72 live proof.
- Narrows `No route to host` wording to the configured endpoint rather than assuming the failed route is necessarily between the hub and the named physical device.
- Retains Markdown table-cell boundaries and measured numeric findings during all repairs.

### Regression coverage

- Adds the complete 0.16.72 live performance answer as a regression fixture.
- Verifies memory, temperature, database, latency, call-count, and busy-rate measurements survive deterministic repair.
- Verifies the recommendation table remains a valid three-column Markdown table.
- Adds focused tests for the cross-sentence scheduler causal variant and latency-to-timeout suggestion.

### Live acceptance target

Run:

`Analyse my Hubitat performance and recommend improvements.`

Expected architecture remains normally **4 tool calls / 3 model rounds**, with current metrics preserved and no unsupported healthy-limit, bottleneck/blocking, CPU-spike/UI-delay, background-overhead, or timeout-mechanism claims.