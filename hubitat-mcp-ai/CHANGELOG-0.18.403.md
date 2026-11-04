# HomeBrainOS v0.18.403 — Q1 source-qualified telemetry explanations

- Installed v0.18.402 read-only MQTT/health question returned
  an unverified physical/driver-watchdog explanation despite
  host evidence showing a **566.1h vs 45.1h** freshness-clock
  conflict, bounded positive MQTT disconnect history, and
  explicit unverified driver/broker/root-cause fields.
- General final publication boundary checks source identity,
  same-request telemetry clocks, positive disconnect events
  and installed-driver method verification before allowing
  categorical claims of physical failure, last actual packet,
  watchdog mechanism or absence of disconnects.
- Preserves model-authored, explicitly qualified uncertainty
  and read-only next steps; reports private-safe correction
  counts and categories. No additional MCP calls, model
  rounds, device commands or rule-authoring capability.
- Synthetic regression tests cover unrelated device IDs,
  multiple MQTT endpoints, positive event contradictions,
  same-clock-but-unverified physical telemetry, source
  failures and already-supported/qualified wording.

**No post-release live quality or latency measurement yet.**
Original baseline: 36.507s, six model rounds, eight tools.
See `docs/ANSWER-QUALITY-Q1-TELEMETRY-SOURCE-BOUNDARY-20261104.md`.
