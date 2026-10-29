# Hubitat MCP AI v0.18.209 — Live read-contract guidance and evidence frontier

## 29 October v0.18.208 live replay

The latest Google Nest Hub investigation correctly retained device 7934, completed seven successful source reads, published a source-bound causal assessment and skipped model-only synthesis (0 ms). It included 7 closely timed WARN records, 3 near-warning Google Calendar Notifier commands and separately denominated Hubitat Device/App Stats snapshots. The cause remains unattributed because the generic warning does not identify an executed method or incident-time CPU.

The remaining inefficiencies were 2 rejected `hub_get_device` proposals missing their required nested `args.deviceId`, one event-history READ whose result was a subset of an earlier returned sample, and a report that led with the source-code blocker before the actual finding. The run took 22.656 seconds, including 7.384 seconds in the Hubitat Device Stats read; model-facing contracts do not eliminate upstream gateway read latency.

## Changes
- The model-facing MCP read tool descriptors now document *required operation-specific nested arguments* only for operations enumerated by each **live read-only gateway**. This is descriptive: no new gateway, operation, elevated authority, read, or write is introduced. The gateway's actual live JSON schema and independent host validation remain unchanged.
- On a missing-required-fields rejection, contract feedback prioritises the independently verified investigation focus over the first sorted dozen unrelated hub inventory IDs. It provides an explicit `{"tool":"hub_get_device","args":{"deviceId":"<verified focus>"}}` **non-executing** correction shape only when one already-verified device target exists. No model-provided or ambiguous identity can be automatically accepted.
- On a successful device-scoped event-history READ, the model receives a compact *evidence frontier*: the actual returned event count and oldest/newest source timestamps, with a note that re-reading a narrower range yielding the same rows offers no new information. This is advice only, not a blanket ban on reading distinct historical scopes. Source completeness remains false.
- Put the supported incident answer before ancillary driver-code blockers in the source-bound report. No causal claim is strengthened or invented.
- Add regression tests for advertised operation isolation, explicit contract hints, unverified/ambiguous IDs, driver/app type isolation, end-to-end recovery from one malformed device read, and source-window frontier without auto re-reads.

This is an experimental read-only V2 change. Existing evidence boundaries, source receipt verification, runtime-statistics denominators and full host preflight remain enforced. No Hubitat device, rule, automation or production Main Ask change is made.
