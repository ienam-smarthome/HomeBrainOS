# HomeBrain v0.17.69 — Skills Framework

## New
- Bundled, versioned **Hubitat MCP Operating** and **Hubitat Investigator** skills under rootfs/app/skills; only relevant skills are activated and text is size-bounded.
- Skill-aware investigative guidance: live MCP catalog authority, nested native-app configuration, targeted history, read-only permissions and efficient paginated calls.
- Source-typed causal evidence projection ranks recorded command candidates and explicitly surfaces intervening switch transitions and hypotheses without claiming proven causality.
- Producer-first topology plan identifies app-configuration and execution-log source gaps for focused follow-up; never guesses room sensors from labels.
- Model-facing tool contents and final answers now redact common JSON/headers/key-value credential forms. Redaction does not modify the raw Hubitat evidence ledger.
- Added privacy-safe request metrics: `skills_framework_activated` and `skills_topology_plan`.
- Added focused regression suite and architecture docs.

## Validation and limitations
This is a reusable skills runtime and investigative planning framework. It does not grant additional MCP privileges or change Hubitat devices. Historical events and app configuration still depend on what the connected MCP server exposes. Current app settings do not prove execution at a past time; missing logs cannot be recovered by the skill. No durable cross-session memory is introduced. Live verification is required after CI.
