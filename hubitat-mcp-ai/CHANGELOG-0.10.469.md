# Hubitat MCP AI 0.10.469

## Enforce a single immediate controller-history follow-up

Live validation of 0.10.468 confirmed that controller discovery is now working:
the room filter exposed `eventSourceHints`, and HomeBrain successfully queried
same-room dimmer/button devices with `attribute=pushed`.

The remaining defect was fan-out control. The 0.10.467 reservation only became
exclusive after the generic 8-read budget was exhausted. When controller discovery
happened earlier, the pending reservation suppressed synthesis but ordinary reads
were still allowed, so the model queried four dimmers across six model rounds.

0.10.469 makes the reservation an immediate one-read boundary.

### Single ranked controller target

Only the highest-ranked controller candidate from structured room discovery is
reserved. Candidate ordering remains deterministic:
- exact room metadata before label-affinity fallback;
- then the existing stable discovery order.

### Immediate exclusive reservation

Once controller follow-up is armed:
- the very next model-directed read must be `homebrain_device_history` for that
  reserved candidate;
- the requested attribute must be one of its suggested controller attributes;
- after that one attempt, every further read in the same native round and later
  rounds is rejected and final synthesis is forced;
- an invalid competing read consumes the reservation and is rejected, preventing
  the model from bypassing the boundary by trying sensors or other controllers.

This is independent of whether the ordinary 3-round / 8-read budget has already
been spent, so controller discovery can no longer open several extra rounds.

## Live evidence driving the change

The 0.10.468 Bedroom 3 run:
- exposed `eventSourceHints`;
- queried Bedroom 3 dimmer - 1 through - 4 for `pushed`;
- reached 6 model rounds / 20 tool calls / 28.8s;
- therefore proved candidate discovery worked but the follow-up reservation was
  not an exclusive one-read cap.

## Regression coverage

Tests verify:
- the reservation applies immediately even before the generic read budget is spent;
- only the highest-ranked controller candidate is eligible;
- one matching controller-history read succeeds;
- a second controller read in the same round is blocked; and
- wrong target/attribute attempts are rejected and consume the reservation.
