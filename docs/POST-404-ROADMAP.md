# Post-#404 architecture roadmap

PR #404 removed the production grounding monkey-patch in add-on 0.10.314. The remaining work is tracked in this order:

1. **Missing-device `unresolved` classification** — add `device_resolution_missing`, record it for zero-candidate and below-threshold single-candidate resolution, classify it as `unresolved`, and present it in technical metrics. The reviewed patch is ready to rebase as add-on version 0.10.315.
2. **Live cancellation propagation test** — prove a superseded request cancels the real provider/MCP transport operation, not only the coordinating asyncio task; verify the first outcome is `cancelled` and the replacement request completes.
3. **UI outcome formatting** — visually distinguish `success`, `unresolved`, `refused`, `cancelled`, and `failed`; prominently surface verification failures and grounding refusals.
4. **Broaden metrics instrumentation** — cover all discovery paths, every remote MCP call/retry, write verification timing, confirmation expiry during live API requests, and cancellation without double-counting.
5. **Split `mcp_agent_orchestrator.py`** — extract provider loop, confirmation flow, grounding coordination, tool execution coordination, outcome construction, and retry handling incrementally.
6. **Final soak pass** — exact named device, ambiguous device, missing device, grounding refusal, verification failure, expired confirmation, and live cancellation.
7. **Repository cleanup** — remove or archive unused `backend/` and `frontend/` scaffolding, distinguish blocking release scripts from optional soak tools, and automate version/changelog consistency.

Additional documentation maintenance:

- Fold `docs/ARCHITECTURE-MODULE-MAP-UPDATE.md` into the canonical architecture table.
- Replace or clearly relabel the stale repository-level `CHANGELOG.md`.
- Consider a generated roll-up/index for the per-version add-on changelogs.
