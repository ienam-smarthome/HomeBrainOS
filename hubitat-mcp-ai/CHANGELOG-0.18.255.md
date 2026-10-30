# v0.18.255 — Evidence-driven causal discovery in the original MCP agent

## Root cause from live v0.18.254 test
The original HomeBrain agent returned a truthful three-light historical timeline but could not independently investigate the inputs that might have initiated the transitions. The independently source-timed Historical Journal observations were obtained **after** the model had already stopped selecting read tools. In addition, source-class completion was treated as successful task resolution even when `causalInitiatorVerified` was unknown.

## Architecture
- **One evidence-discovery cycle, not a second agent:** Reuse the original unified MCP tool catalog, model rounds, source receipts and proof boundaries. A bounded Historical Journal recovery now runs after model-selected read rounds, when verified targets are available, and may run once at the model's voluntary no-tool checkpoint. The archive query is idempotent and tightly scoped by verified device IDs, dates and time zone.
- **Recovered observations become model-visible evidence:** A compact typed checkpoint lists source-timed ON/OFF observations, reception-only observations, known Hubitat commands and journal gaps; it tells the original model to choose the most discriminating next *authorized read-only* input/controller history when no independent input source has been checked. No specific sensor, controller or tool ID is guessed.
- **Advance past duplicated reads:** Existing `unified_investigation_followup` no longer demands the same native switch history indefinitely when the independent Journal recovered source-time switch evidence. It advances to missing input histories and then to controller/app execution provenance, with existing tool and round budgets.
- **Outcome reflects unresolved causality:** When a verified target timeline contains ON observations whose initiating commands remain unknown, `investigation_coverage.questionResolved=false`, `rootCauseVerified=false` and `status=partial-evidence`, even if the necessary source classes were queried successfully. The request outcome is **unresolved**, not a misleading green success.
- **No new unsafe authority:** No additional MCP capability or external source access, no live Hubitat changes, no modification to writes or confirmation flow, no keywords hardcoding Bathroom/Hue/LWR01, no invented source histories.

## Tests
- Cross-source archive to model discovery checkpoint
- Journal source versus reception timestamp non-equivalence
- Missing independent inputs then controller followup
- Do not repeat already recovered actuator switch histories
- General request outcome classification and precedence
- End-to-end repository regression / Home Assistant add-on smoke validation

## Remaining boundary
This improves when the original model *can choose* meaningful follow-up reads. It does not prove that a given model will always select the best tool or that upstream HA/Hue/SmartThings traces exist in its available permissions. Causal initiators remain unverified without source-attested execution evidence.

Merge only after required GitHub Actions are green. Live add-on update remains a separate user action.
