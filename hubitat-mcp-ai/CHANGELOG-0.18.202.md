# HomeBrainOS v0.18.202 — discrete warning occurrences and source blockers

## Live evidence reproduced

The 29 October 2026 01:07:58 Native V2 test returned 5 separate Google Nest Hub device 7934 generic excessive-load WARN records between 28 October 19:55:19.194 and 29 October 01:03:20.292. The earlier evidence adapter projected only the group endpoints; the incident audit wrongly treated the whole interval as one continuous warning and assessed command/event proximity against that span. Its 10 device events had no independently verified app-issued commands, but did include volume=15 then 10 around the latest warning. The device configuration read had driver source status unavailable, no attested driver ID; two attempted event history reads were locally rejected for wrong gateway and missing target scope.

## Changes

- Preserve at most 48 distinct source-reported warning timestamps per compact WARN/ERROR group, with count/cap and explicit timezone and sampling limitations. The group oldest/newest remains available for auditing; it is not a continuous incident.
- For generic device WARN attribution and event coverage, use the newest *actually returned warning timestamp* as a discrete occurrence if available. Older synthetic grouped-only evidence retains its bounded fallback. Record the full grouped sample separately, describe why source observations do not establish continuous hub load, and compare nearby device states and commands to the chosen occurrence rather than an arbitrary 68-minute span.
- Preserve the boundary between zero verified app-issued commands in a bounded event sample and the device having no automation callers across historical samples.
- Distinguish a configuration read which explicitly reports `driver_source_metadata.status=unavailable` and lacks a source driver ID. Publish this as a source-backed blocker, not a guess about internal method implementations. The V2 model remains free to investigate via other independently verified READs.
- Rejected tool proposals receive, when available, **only** independently attested read gateway names; no discovered management/mutating gateway is offered. Missing target-scoped event history returns the concrete required `deviceId` read-only contract, without filling it in or executing a tool.
- Synthetic regression tests reconstruct five discrete WARNs, two near-warning volume states, no app command issuer, missing driver source, legacy group-only evidence, safe gateway alternatives, and rejected unscoped event read contracts.

## Scope and limits

No Hubitat writes; production Main Ask unaffected. The root cause of Google Nest Hub hub-load warnings remains unverified. Driver source and incident-time execution measurements remain unavailable from the provided test; the release only improves time-aware reasoning, read contracts and limits. Source clock/timezone alignment and history completeness remain unverified.

## Acceptance

All GitHub release workflows and Python tests pass before merge. After upgrade, run Native V2 on a new warning and check that the report identifies a discrete most-recent warning rather than implying continuous load, exposes driver source unavailability, and correctly distinguishes absence of observed calls from absence of automation callers. Live improvement cannot be declared from CI alone.
