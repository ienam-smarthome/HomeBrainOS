# Hubitat MCP AI 0.16.58

## Structural performance grounding

- Performance synthesis now preserves measured facts while localizing only unsupported implementation-mechanism, outcome-causality, or tuning clauses.
- Configuration advice is handled structurally instead of by global whole-line replacement: recommendation tables keep their Component and Expected Impact cells, while unsafe Action cells are replaced with inspection-first guidance.
- Analysis bullets keep measured percentages, call counts, and execution times even when a later unsupported sentence is downgraded.
- Decorated action headings such as `### 🛠️ Recommended Optimisations` are recognized.
- Recommendation detection covers review/inspect/investigate/check/verify/audit wording and passive reduction language as well as direct edit/set/change verbs.
- Unsupported timeout/API latency/polling/config-push/retry/reconnect/reporting mechanisms are localized independently of narrow lead-in phrases such as `often indicates`; variants such as `typically indicates` are covered.
- Strong unsupported performance-outcome claims such as `primary source of hub stutter`, `common cause of event-bus congestion`, and `most likely candidates to cause lag` are downgraded while measured values remain visible.
- Rule recommendations tied to every sensor/power event are inspection-first unless the relevant rule configuration was read in the current turn.
- Explicit conditional analysis such as `could block execution threads if calls are synchronous` remains allowed.
- No additional Hubitat reads are introduced; evidence collection and threshold compaction are unchanged.

## Live regression coverage

Tests reproduce both 0.16.57 live response shapes, including LG `typically indicates` timeout/thread-blocking language, power-socket event-bus congestion, SenseCap polling/config-push variants, Life360/Octopus polling advice, LG sync/async investigation, and MCP rule advice tied to every power-value change.