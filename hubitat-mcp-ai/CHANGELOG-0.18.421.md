# HomeBrainOS 0.18.421 — external Hubitat incident recorder

- Add opt-in external 30-second live Free OS memory and latency recorder in Home Assistant add-on, with source-limited five-minute Java/CPU sampling.
- Preserve observed samples and two-failure connectivity incidents in bounded SQLite retention; do not infer reboot or Metaspace OOM from timeouts.
- Add same-origin read-only status/history API and compact Hub Diagnostics charts to HomeBrain UI; charts read SQLite only.
- Restrict monitored hub destination to local private IPv4 and disable redirects/proxies; no device commands, hub-side apps, or increased Hubitat JVM workload.
- Maintain default-disabled behavior; add setup guide and mocked unit tests.

Operational validation and performance impact on the user's C8 Pro remain unverified until installed.