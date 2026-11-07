# HomeBrainOS v0.18.455 — Source-attested causal shadow on autonomous history-only routes

## v0.18.453 installed acceptance and incident-independent failure

The 7 November 10:54–10:55 GMT read-only latest-OFF live response deployed
v0.18.453. It reported a source-confirmed OFF at 00:30 GMT and an unknown
upstream initiator, but its Technical JSON contained no
`evidence_validation.claim_evidence_shadow`. The runtime attached only
model-generated `investigation_coverage.hypothesisComparisons` (no
`domain=causal_provenance`), and did not run the optional
`homebrain_causal_secondary_correlation` helper. The response builder and
adapter both incorrectly treated those optional hints as prerequisites.
This was a **failed installed source-real acceptance**, regardless of green
synthetic CI.

The actual source receipts had one targeted device (ID 7828), 11
native-derived switch boundaries, latest OFF at 2026-11-07 00:30:00.023
GMT, six OFF observations in returned history, seven command-off records,
and two matched earlier button commands under the 2-second matching
convention. A successful general past-log request for 23:50–00:40 GMT
included the focal OFF and reported zero matching rows with historical
completeness unverified. A simultaneous hubEvents request was separate.
No native focal sensor history was read. No evidence proved the upstream
controller, app/rule execution, remote or external integration. The
answer's statement that notified listeners 'did not initiate it' was
stronger than the recorded listener role permits.

## Generic integration repair

- Extend `claim_evidence_adapter.py` to derive the latest requested
  OFF from one successful source-reported switch history and one uniquely
  matching targeted device when the optional correlation tool is absent.
  Require explicitly causal, latest-OFF **read-only question scope**,
  target label membership, typed native device reporter and source time.
  This is not a general model-text focal-event selector.
- Keep the existing host-correlation focus path as the preferred source.
  Include `focal_source` provenance:
  `host-correlation` or `source-history-latest-off`, never a claim that
  native device retention was complete.
- In `api_response_builder.py`, allow the same attested packet to
  identify a read-only causal response when the outcome's model-proposed
  coverage lacks a domain marker. Reuse this packet for the existing
  source-role guards and `claim_evidence_shadow` output. Report a
  privacy-limited `claim_evidence_shadow_status` on attempted but
  unverified source focus; do not silently mark quality as passed.
- Extend the global listener-role guard to reject unsupported
  'listeners reacted; they did not initiate' statements. A listener can
  be downstream in a recorded event and still have other unknown action
  paths. This does not assume the listener *did* initiate anything.
- Preserve existing claim-v2 protection against zero-page absence,
  unverified clocks, model-chosen pairing denominators, collector-received
  sensor edge times, and incomplete command history. Existing
  `model_claims_assessed=false` and `shadow_only=true` remain explicit.

## Acceptance

Synthetic live-shaped fixtures cover exactly the optional-domain and
optional-correlation omissions, 6/2/4 returned transition-command pairing,
one focal general past-log request, zero direct native sensor windows,
one source-attested latest OFF and known unresolved cause. Negative
tests protect absent/ambiguous target, unsuccessful history, wrong user
intent, unrelated requests, writes and confirmations; existing broad
tests cover normal host-correlation routing and other domains.

Merged [PR #1514](https://github.com/ienam-smarthome/HomeBrainOS/pull/1514) only after all four required checks passed on exact tested head `33d9d911377cb76c9a8fabcec56c25deaceca132`. Release assurance reported **6,747 passing Python tests**, two nonblocking warnings and successful container smoke/metadata; Hubitat MCP AI tests, HomeBrain validation and Answer Quality integrity also passed. Squash merge main commit: `adf9e5ca1ff046ca85c8687d5b4010e9bb8c76fc`. CI success alone is **not** acceptance of a deployed assistant.
After installing v0.18.455, rerun the original latest-OFF question and
check both the answer and typed shadow diagnostic. For that same historical
packet, expect `focal_source=source-history-latest-off`, six reported OFF
transitions, two paired within 2 seconds, zero actual native sensor windows,
and one general past-log request containing focal OFF. Retained history and
which tools the autonomous agent calls can change, so exact source-real
counts must be interpreted from fresh receipts.
