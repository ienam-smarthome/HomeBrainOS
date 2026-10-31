# HomeBrainOS v0.18.289 — Stage 4I host-source atomic proof obligations

**Offline, additive source-only evaluation foundation. No live activation.**

- Introduces `stage4_atomic_proof_obligations.py` as a pure,
  bounded, fail-closed host-source proof validator for individually
  typed propositions with exact canonical evidence witnesses.
- Source-typed `recorded_event`, `recorded_issuer`,
  `recorded_clock`, explicit `recorded_gap` and safe
  host `packet_limit` assertions can be independently checked.
- `physical_effect`, `upstream_cause`, `absence_of_event`,
  and `complete_history` remain **unproven** from Stage 4A
  packets; cited commands, reported sensor events, issuer app IDs
  and timestamps never establish those extra propositions.
- Constructed cross-domain regressions challenge false sensor/
  humidity cause, invented boiler response, source-clock confusion
  and archive gaps. Reports contain only aggregate proposition
  verdict counts and no user/device/source text.
- A separate static reference benchmark counts false accepts and
  false rejects on *curated constructed atoms*. It does **not**
  establish that real model-authored prose was parsed correctly,
  verify packet authenticity from external sources or provide
  independently authenticated live truth.
- Stage 4H actual model finding motivating this change:
  even two agreeing reviewers **falsely accepted one of three
  unsafe synthetic complete answers** and rejected three of four
  adequate answers. These reviews are not a publication gate.

**No active agent, prompt, model routing, V3 publisher, Home Assistant,
Hubitat or device control changes.** Every proof report explicitly
says no free-form prose was semantically verified and publication
approval is false.

See `docs/INVESTIGATION-STAGE-4I-ATOMIC-PROOF-OBLIGATIONS.md`.
Rollback: revert the additive source-only PR.
