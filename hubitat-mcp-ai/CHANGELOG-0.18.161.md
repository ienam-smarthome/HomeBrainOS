# HomeBrainOS 0.18.161 — Historical source first, before AI

## Live regression diagnosed

The 27 October v0.18.160 dated Bedroom 3 Mesh investigation took 72.620 seconds:
- 20.554 s identity inventory over 5 pages (204 devices);
- model round 0: 16.426 s, **zero canonical source observations**;
- model round 1: 35.004 s timeout with 21 historical records;
- 2 MCP reads, a historical device event page and an unsupported-for-projection
  device-dependents operation; no stored app-config retrieval.
- It recovered the 12 October 01:30:01 BST command from issuer 3950,
  a reported switch-off 0.17 s later and healthStatus=offline at 01:33:46 BST.
  These support an OFF-adjacent connectivity event, not physical causality.

## Architectural fixes

1. **Remove arbitrary 7-day incident-first cutoff**. Explicit historical
   windows are now scoped and validated against the current live gateway
   argument schema, including optional since/until and the genuine advertised
   hoursBack/limit limits. Reject unsupported or ambiguous scopes; no broad
   accidental history or write escalation.
2. **Evidence precedes planning for old dated incidents**. A successful
   manifest-approved historical preflight now runs before source-identity
   and app-configuration enrichment and before the first model planning round.
   A late ON attempt does not replace the original event-attested issuer.
3. **Projectable-source contract**. Model plans and host read reviewer now
   accept read suboperations only where V2 has a reviewed typed source
   projection, preventing a successful yet evidentially useless
   hub_list_device_dependents call from consuming the read budget. Extending
   source coverage requires adding its reviewed projection, not trusting raw
   tool text or arbitrary model descriptions.
4. **Regression tests**: replay of the 15-day-old incident, live-schema
   maximums, ambiguous targets, write gateways, unsupported read operations,
   event-attested controller 3950 and typed current configuration before AI.

## Safety and limits

- No live Hubitat device writes; the V2 read-only gate remains strict.
- An issued OFF and a subsequent Hubitat switch=off report do not establish
  independent physical state or confirm AP/network topology.
- Source history is not complete unless independently verified.
- The upstream 35-second model timeout and ~20-second cold identity inventory
  are not solved by this release. Its objective is to prevent expensive
  *empty-case* planning and restore historically relevant source enrichment.
- CI synthetic replay is not a live latency measurement.

## Live acceptance

After updating the add-on, run the same dated read-only question. Expect
historical device-event reads and an event-attested config read for issuer 3950
before the first model planning call, subject to the live manifest/read budget.
Compare planning rounds/latency, `bootstrap_diagnostics`,
`current_app_identities` and main report. Do not alter hardware or apps.
