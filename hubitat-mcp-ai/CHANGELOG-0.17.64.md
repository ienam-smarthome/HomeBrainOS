# HomeBrain v0.17.64 — evidence joining, configured sensor selection, model budget

## Typed Hubitat event evidence

- Join an ID-scoped direct `hub_list_device_events` source receipt to a
  deterministic `homebrain_device_history` row that carries the events, when
  the direct tool receipt intentionally omits large event details.
- A join requires exact resolved target label, equal history lookback and
  returned event count, and one immediately following derived receipt
  within ten seconds. Ambiguous or mismatched source pairs are rejected.
- Expose `normalizedDeviceHistory.joinedDerivedHistory` and
  `eventSource: verified-direct-derived-receipt-pair`. The existing
  evidence-first final response can then report the full verified scope,
  command count, state events, history integrity and unknown physical state.
- A joined event stream is still bounded Hubitat history, not proof of a
  physical MQTT frame or end-to-end command acknowledgement.

## Configured sensor candidates before room-only discovery

- For a light with declared known-automation topology, search the
  authoritative cached device identities for capability-backed, concrete
  motion/presence sources that the rule configuration actually references.
- Promote such configured trigger candidates into the first two bounded
  historical sensor probes ahead of generic room-first candidates.
- Do not promote unrelated cross-room sensors, configuration-only names
  without device IDs, or non-occupancy devices to historical evidence.
- Report the selected candidate IDs and incomplete configured-source
  coverage via `sensorSelection`; configuration is a discovery hint,
  not execution proof.

## Model-round efficiency

- Cap additional model-directed tool rounds at six for read-only, deep
  causal investigations of explicitly named historical clock times.
  Focused host evidence collection and the verified final-answer
  coordinator remain available if the exploratory budget is exhausted.
- Do not change execution limits for writes, confirmations, general
  inventory reads or untimed investigations.
- Count `causal_configured_sensor_prioritized`,
  `causal_read_round_budget`, and
  `causal_read_round_budget_exhausted` separately.

## Safety and scope

Read-only code changes. No Hubitat devices, switches, automations or settings
are altered. CI uses synthetic event receipts; real-world source availability
and any latency savings require tests on the running HomeBrain add-on.
`general_task_engine_enabled` remains opt-in.
