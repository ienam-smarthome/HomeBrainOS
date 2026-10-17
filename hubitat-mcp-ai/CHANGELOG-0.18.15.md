# 0.18.15 — Carry requested comparative hypotheses through specialised investigations

## Live finding
In the 0.18.14 Bedroom 3 Mesh test, device-health evidence and telemetry clock boundaries were handled correctly, but the answer did not compare the three requested alternative causes. Existing causal routing skipped the general semantic task planner. The final safety-oriented typed history renderer could also replace model prose. A repeat produced four Gemma model rounds and a 34.5-second response while still returning a cautious, partial outcome.

## Architectural improvement
- A narrowly scoped opt-in classification recognizes investigations that explicitly ask for competing explanations or alternative hypotheses. The existing semantic planner runs in that case, including when the protected causal history route is chosen; ordinary one-step causal requests stay on existing efficient fast paths.
- Store the bounded candidate explanations in per-request context, not tool evidence. The model is proposing hypotheses, not supplying facts or authority.
- At finalization, compare proposed discriminating questions with actual current-request source-read receipts and add the bounded comparison to structured investigation coverage, with every hypothesis unverified.
- Preserve that tentative section after the existing typed device-history safety projection, without replacing or weakening reported telemetry facts, historical evidence limitations, or stop rules.
- Do not trigger additional MCP source scans, extra tool permissions, writes or confirmation bypasses.

## Limitation
This makes model-proposed alternatives visible and checks which source classes were queried. It does not yet test typed contradictory evidence, rank causes empirically, establish MQTT broker status or prove device command delivery. Those belong to the next evidence-comparison phase.

## Verification
Regression coverage for explicit-vs-routine question routing and safe alternative preservation in the final API. Full CI gates required before merge; live Home Assistant verification required after installation.
