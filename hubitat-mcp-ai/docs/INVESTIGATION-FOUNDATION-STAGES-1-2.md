# Investigation foundation: Stage 1 and Stage 2

Pinned baseline: HomeBrainOS v0.18.272 at Git commit
614a3794cf9106c7e1b14f7afd0fadbffca7e39b.

## Shadow-only boundary

This change adds an immutable, bounded canonical evidence and identity VIEW
over already recorded successful read receipts. It is additive and is not
invoked from the production agent or publisher. No tool calls, writes, HA or
Hubitat changes, database migrations, configuration flags, new HTTP endpoints,
routing changes, or new causal publication are introduced.

The existing causal graph, witness ledger, time-window and historical journal
recovery, scoped device resolver, model tool loop and legacy publishers remain
unchanged. This is not a replacement for their safety checks.

## Typed representation

* VerifiedIdentity: device/app ID, safe label, proof source, receipt index,
  provenance rank. Highest rank wins only if unambiguous. Conflicting
  equal-ranked labels fail closed. Model text cannot attest an identity.
* CanonicalEvent: entity ID, attribute, scalar value, role (reported-state,
  input-report, issued-command), source-reported versus independently
  source-recorded versus collector-received time, and receipt provenance.
  Explicit command issuer IDs are distinct from event-notified apps.
  Physical acknowledgements remain unverified.
* EvidenceCoverage: journal gaps and truncation, explicit incomplete flag.
  Empty or short native history does NOT prove absence of old events.
* CanonicalEvidenceView: frozen tuple-backed records; bounded JSON-compatible
  projection for future shadow comparison. It cannot execute anything.

A native device switch report does not prove physical switching, a command
after the ON report does not initiate the earlier ON, and same-receiver sensor
timing does not establish upstream issuer.

## Anonymised baseline

Existing five-cycle 30 October light incident fixture:
test_v3_reception_evidence_018267.replay() uses renamed devices and sensors.
The Stage 1 baseline asserts five ON/OFF cycles, including 15:07:14-15:11:09
(3m 56s), and preserves original-issuer uncertainty. Journal source-clock
and collector-received observations remain distinct.

The Stage 2 fixture additionally covers scoped device/app identity, paired
named history and native ID scope, app issuer versus notified listener,
unsafe/mismatched names, ambiguous identity, out-of-scope rows, naïve
timestamps, coverage gaps, truncated results, and HVAC/contact/power data.

The observed real v0.18.272 baseline was 7 model rounds, 32 tool calls and
55,824ms. This PR does not change the live path and makes NO performance or
answer-quality improvement claim.

## Acceptance criteria and next steps

1. Python compilation, new tests and existing CI release gate all pass.
2. Existing publisher and historical-coverage semantics stay unchanged.
3. No source identity emerges from unscoped/model text or listener metadata.
4. Collector timestamps cannot become source time or physical ACKs.
5. Runtime/production calls must not import or execute this module yet.

A later separately reviewed PR can compare canonical projections against
current causal evidence and witness graph in *shadow* and benchmark overhead.
Only after that should work on active investigation planning and natural
model-authored evidence-validated narratives be considered.

## Rollback

Delete/revert these additive files or close the PR. No live deployment or
configuration changes require rollback.
