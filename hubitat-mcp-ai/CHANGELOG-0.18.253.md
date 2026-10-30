# v0.18.253 — Native source-role graph reaches the original causal agent

## Why this release
A live investigation retrieved device-scoped `hub_list_device_events` histories, motion input timelines, and a verified app-issued Shower Light OFF command. Its model still claimed that the Bathroom lights were *operated externally*, while the evidence coverage explicitly marked external/upstream origin as unverified. The existing provenance guard only projected `homebrain_device_history` wrapper observations, ignoring the native device-scoped source rows used in this successful investigation.

## Unified source-role contract
- Normalizes successful, read-only **native device-event receipts** and deterministic `homebrain_device_history` receipts into a single bounded typed source-role graph, without inventing any upstream actor.
- Reports source roles separately: bridge or device **reported-state**, app **notified-listener**, and app **issued-command**. These have distinct directionality and never imply the same causal role.
- Requires event-history reads to name the independently scoped `deviceId`. A deterministic label-only history must match one unique source-verified targeted lookup. Whole-hub queries, failed reads and mutating receipts cannot introduce per-device source roles.
- Deduplicates native and wrapper observations by identity, timestamp, attribute and value; exposes bounded graph edges, direct command counts and evidence-coverage limitations.
- Makes the same source-role graph available to the existing model-directed checkpoint and natural-language final synthesis via the original agent; no new LLM route, parallel investigation engine or tool permission.
- Ensures causal validation can now challenge unsupported external-control claims and categorical command absence in multi-target investigations based on native evidence, preserving genuine commands and timelines.
- Adds cross-domain tests for native receipts, direct command source, downstream listener roles, failed/unscoped/truncated history, deterministic identity joining, real unsupported external-control wording, and synthesis validation.

## Safety & limits
These are **read-only reasoning and validation** changes. They do not determine which Home Assistant/Hue controller actually initiated unverified transitions; actual upstream tracing still requires a verified external source and permissioned tooling. A successful bounded Hubitat history read does not guarantee complete retention.

## Merge policy
Full CI all-green required; live HA/Hubitat installation remains separate.
