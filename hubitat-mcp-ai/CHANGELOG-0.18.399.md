# HomeBrainOS v0.18.399 — timed Internet summary preflight

## Observed baseline

The first live Google TV timer request on v0.18.398 took **38.16 seconds**
to offer confirmation, with 37.95 seconds attributed to MCP HTTP. Once
confirmed, the command and driver-deadline verification completed in **1.8
seconds**. The two-minute scheduled block subsequently fired and Hubitat
reported MAC blocking plus conntrack flushing; the owner manually restored
Internet access after the test.

## Changes

- Replace the redundant all-device **detailed** manifest admission read
  with a single lightweight, authorised, filtered `hub_list_devices`
  **summary** scan. Request only id, label and driver, in bounded pages.
- Preserve driver-attested identity, ambiguity checks, protected-system
  exclusions, expected-ID confirmation snapshots and post-approval timer
  deadline verification. A mixed/partial/unparseable summary page fails
  closed before confirmation instead of authoring an RM fallback.
- Enter the direct driver path only where both the read and command
  gateways are installed. The existing native Rule Machine route remains
  for legacy/non-Cudy devices and unsupported gateway configurations.
- Add privacy-safe request metrics `timed_internet_summary_preflight`,
  `timed_internet_summary_preflight_failure`, and
  `timed_internet_preflight` milliseconds.
- Add offline regression tests for the summary-only flow (no detailed
  manifest), multi-page filtered lookup, incomplete inventory refusal,
  legacy fallback and the existing confirmation/replay safety contract.

**Verification boundary:** This is a code-level latency optimisation. The
post-update live preflight latency is not measured until a controlled
v0.18.399 request and its Technical JSON metrics are captured. CI results
are not a substitute for live measurement. No Hubitat, HA or router
changes were made by this PR.
