# HomeBrainOS 0.18.423 — CPU load as a percentage

- Add five-minute CPU load equivalent (%) to the HomeBrain external Hub Diagnostics summary and chart selector, alongside raw five-minute CPU load.
- Use the existing Hubitat-native 5-minute load average and a configurable logical processor count (default 4 for C8 Pro).
- Formula: **load average ÷ logical processors × 100**. For 0.76 load on a four-core hub, this is 19.0%.
- Clearly label this as **load equivalent, not measured CPU utilisation**; values above 100% are retained rather than misleadingly capped.
- Preserve the original unmodified five-minute CPU readings in SQLite; derive percentages when serving the read-only status/history responses.
- No new Hubitat queries, event subscriptions, or collector schedule changes.
- Include calculation, missing-data and UI regression tests.