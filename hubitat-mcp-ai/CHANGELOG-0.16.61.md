# Hubitat MCP AI 0.16.61

## Evidence-repair cleanup

- Performance source-absence detection now requires explicit absence predicates instead of treating generic `not ... logs/performance` wording as a missing-source claim.
- In substantive performance answers, a contradicted source-absence sentence is removed locally instead of injecting serializer repair prose into a valid device or log observation.
- The pure false-no-data fallback from 0.16.59 remains intact and emits one compact deterministic correction when successful current-turn performance sources were actually read.
- Legitimate negative causality wording such as `does not establish that the logs caused ...` is no longer misclassified as source absence.
- Conditional claims that measured latency `can/could/may/might impact ... responsiveness` are localized to investigative wording that explicitly says the impact is not established.
- No additional Hubitat calls are introduced.

## Live regression coverage

The regression suite reproduces the 0.16.60 Halo evidence-repair leak and the residual LG responsiveness wording while preserving the earlier false-no-data protection. The full release suite contains 1,483 tests.
