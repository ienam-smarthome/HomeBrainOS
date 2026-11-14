# HomeBrainOS V2 alpha.83 — source-only System Health and named overview pills

**14 November 2026 — V2 only.** The user requested more actionable, named Home Overview summaries without extra hub load or Ollama credits, followed by a **System Health** tab that includes optional troubleshooting. V1 `hubitat-mcp-ai/` remains unchanged.

## What the UI shows

The existing read-only overview retains lights ON, active motion, low batteries and inspected inventory, adds **open contacts**, **water detected**, **heating reported**, **explicitly reported offline** and **other ON switches**. The eight device-state pills show a compact count, number of devices reporting that attribute, the first named members and an expandable name list. A ninth tile shows inspected device count and source total. Click-to-expand uses local DOM only; it is **not an Ask question**.

The new **System Health** tab groups the same source data into **Needs attention** (low batteries, open contacts, wet sensors and offline-reported devices) and **Currently reported** (lights ON, active motion, heating state and other ON switches). It displays the original observed timestamp, inventory coverage and names from the same source; absent readings are shown as unknown/unsupported, not zero or healthy. Names are capped at 250 per metric and omissions are reported. No device cause, health conclusion or underlying physical effect is inferred.

The **Troubleshooting** area provides explicit owner-invoked shortcuts for lights/motion investigations, heating, missing telemetry and the existing Diagnostics tab. The first three *only prefill the Ask input*: they never submit a model request. Selecting Hub Diagnostics navigates to the pre-existing diagnostic route; it has its original read-only data loading rules.

## Unchanged load and payment boundary

- One existing `/api/overview` request at the same page lifecycle and the same optional manual Refresh overview button. The native handler still does **one source inventory call** (`hub_list_devices` directly, or the advertised `hub_read_devices` gateway leaf), plus the original MCP catalog discovery. The new categories are computed in `home_overview.summarize_device_inventory` from the **same returned `devices` list**.
- **No extra scheduled poll, refresh interval, recorder access, device status read, hub command, V1 audit, cloud model call or new runtime dependency** is introduced.
- Opening System Health, expanding/collapsing pills, or preparing a troubleshooting question is DOM-only and costs **zero Ollama credits**. The owner must press Ask to invoke the model, which can have model costs depending on the route.
- Neither UI nor server reads device *history* for System Health. A snapshot is not proof of sensor freshness, connectivity or why a state occurred.

## Provenance and limits

A count of zero means no positive matching state **among devices with recognized reported attribute values**. With no supported values, the UI uses a dash instead of declaring zero. `healthStatus=offline` is explicitly reported status, not proof the node disconnected; absent or stale telemetry is not silently converted to offline. `thermostatOperatingState=heating` reports current operating state, not a computed heating-demand conclusion. `water=wet` and `contact=open` may warrant checking but are not independently verified physical incidents. ON switches without positive lighting identification are separated because they may be plugs or other actuators. Coverage totals and `members_omitted` remain visible for the source-limited results.

## Implementation and checks

- `hubitat-mcp-ai-v2/rootfs/app/home_overview.py`: additional attributes, bounded names and coverage, unchanged `read_overview` native method.
- `hubitat-mcp-ai-v2/rootfs/app/ui.html`: nine named pills; cached System Health findings, supported-state warnings, optional prepared read-only questions and existing diagnostics navigation. Existing Chat/AI Evaluation and device action approval paths are unchanged.
- `hubitat-mcp-ai-v2/tests/test_system_health_snapshot.py`: entirely fictional device inventory, positive/unknown attribute cases, bounded names and one source-native call.
- `hubitat-mcp-ai-v2/tests/test_ui.mjs` and `tests/browser_smoke.py`: DOM-only disclosures and System Health tab, fixed original inventory request count, no `/api/ask` on panel opens, and explicit prefill-without-submit.
- `scripts/capture_v2_command_ui_screenshots.py`: disconnected Chromium screenshots and actual browser-computed contrast audit in light/dark, desktop/390px, including System Health.

The code and CI do not interrogate any installed Hubitat, Home Assistant, Ollama, cloud account or private source receipts. These fictional checks are a structural gate only. After updating, inspect named pills and the System Health tab in the installed UI, confirm snapshot counts/coverage against source, then optionally trigger a **user-directed read-only investigation** via Ask. None of these coached checks count as blind Gate B.

**V1 remains exactly as previously deployed. No paid-cloud model routing changes.**
