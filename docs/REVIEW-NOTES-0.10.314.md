# Review notes for 0.10.314

The external repository review verified the grounding-factory direction and identified two documentation gaps:

- The canonical architecture table states twenty-six runtime modules, while the maintained `hubitat-mcp-ai/rootfs/app/` set contains thirty-four.
- Eight live modules are missing from the table: `homebrain_agent.py`, `token_aware_context_policy.py`, `provider_token_estimator.py`, `live_evidence_authority.py`, `final_answer_coordinator.py`, `request_metrics.py`, `technical_metrics_presenter.py`, and `api_response_builder.py`.

`docs/ARCHITECTURE-MODULE-MAP-UPDATE.md` records the corrected roles using the post-#404 factory architecture. `docs/POST-404-ROADMAP.md` records the remaining work in dependency order, with the reviewed missing-device outcome patch first.

The canonical `docs/ARCHITECTURE.md` table should be regenerated from `scripts/analyze_imports.py` in a dedicated documentation consolidation change, avoiding stale wording from the pre-#404 monkey-patch implementation.
