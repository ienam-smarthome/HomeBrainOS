# 0.17.85 — General investigation evidence checkpoint (first phase)

## Architecture goal
HomeBrain should reason about the user's *actual question* and the best available MCP evidence, not just complete a device-specific checklist. This release introduces an evidence checkpoint and source-selection continuation across investigation domains. It does not promise answers to inaccessible questions and does not establish historic physical causation from collector reports.

## Behaviour
- Adds `investigation_checkpoint.py`: a short, typed, source-scoped receipt ledger with checked/error signals, observed counts, source timestamp coverage gaps and explicit repeat suppression. Raw log messages, private configuration and secrets are excluded.
- Adds `ToolDiscoveryCatalog.activate_investigation_read_view`, exposing only **actually installed and read-classified MCP tools**, with a bounded registry; management/write tools remain unavailable to the reflection phase.
- For explicitly dated historical ON investigations with incomplete verified state evidence, the prior immediate deterministic stop can hand off to up to three **read-only model/tool rounds**, using existing discovery and tool schemas to choose the most discriminating reachable evidence. The trusted partial explanation remains a mandatory synthesis boundary.
- For structured telemetry, manual lockout and scheduler investigations, a model that tries to stop before any essential source class was queried gets one evidence-checkpoint opportunity to pursue a scoped read. Checked-empty or failed sources are not treated as positive evidence.
- Independent host-side enforcement rejects write-classified calls during reflection, even if a tool was later discovered; existing controls and confirmations are unchanged.
- Final evidence synthesis uses the established final-answer coordinator, current-request receipts and validation; an explicit historical verification limitation is appended when the original focal ON is still unverified.

## Limitations
- This is **not** yet a full stateful multi-hypothesis planner; one checkpoint helps the existing model reason further. The safe-read registry and overall request budgets still limit reachable sources.
- MCP capabilities and data access remain authoritative; this adds no access to Hue/Aqara/MQTT brokers if those are not exposed. The journal still does not guarantee completeness.
- Current app configuration and no-message logs cannot establish a prior command initiator.
- Inspect real examples from different domains before claiming parity with Claude. Measure answer quality, correct source choice, contradiction handling, tool budget and hallucinated tool attempts, not merely number of tool calls.

## Regression plan
- Dated light ON with archived OFF/ON/OFF/ON: examine model-selected next evidence, cite uncertainty, no unverified cause promotion.
- Offline or powered-off MQTT device: distinguish telemetry freshness from network reachability.
- Motion lockout: align OFF, button, permitted sensors, app execution decisions and history gaps.
- Scheduled jobs: require owner metadata before attributing CPU/busy time.
- Rule Machine fault: distinguish configured action, execution evidence and ability to write.
- Secret-bearing tool payloads: never expose credentials in checkpoint, model prompt or output.

No Hubitat device, rule, database schema, journal retention or user security setting is changed.
