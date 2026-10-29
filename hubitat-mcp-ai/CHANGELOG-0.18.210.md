# Hubitat MCP AI v0.18.210 — Source-path failure receipts and incident relevance

## Evidence from live v0.18.209 test (29 October 2026)

The model autonomously completed 9 MCP READ attempts: 8 successful, 1 upstream `hub_get_device` failure, plus a blocked duplicate proposal. Every target and app ID was independently verified. It observed 7 Google Nest Hub warnings in a 9.836-second cluster, 3 close Google Calendar Notifier commands and cumulative device/app runtime snapshots; verified focus stayed 7934. No bad argument contracts, no repeated event evidence and no model-only final synthesis occurred. Total elapsed time 32.858 seconds, including 7.522 seconds in upstream Device Stats.

Two source-diagnostic issues remained: the model tried `hub_get_device(deviceId=7934,mode=configuration)` but the gateway returned an error, while `source_path_readiness` wrongly called configuration 'not yet inspected'; and a source-attested `hub_get_source(type=app,id=4080)` succeeded as a gateway operation but returned **no inspectable source code**. The main answer also mentioned '0 commands at the selected warning timestamp' despite the already-verified three commands in the surrounding warning cluster, distracting from its strongest temporal lead.

## Changes

- Preserve narrow `read_filters` (verified device/app ID and mode only) in failed read receipts. A failed, identity-matched **configuration** read now records `driver_configuration_read_failed` instead of suggesting the same mode has never been tried. A regular device read or a failed read for another device cannot trigger this state. Successful complete/incomplete configuration responses still take precedence. The host does **not** retry, repair, or fabricate the result.
- Show the verified failed configuration inspection as a bounded gateway evidence limit, without inventing a driver ID, assuming nonexistent code or calling the hub faulty.
- Add `caller_source_inspections` to the generic incident packet for only independently verified calling apps with an identity-matched source read. Explicitly distinguish a successful gateway source request from actual available inspectable app code. A source-unavailable app inspection cannot establish a device-driver callback; no raw code, URLs or private args are published.
- When individual warning occurrences form a source-timed cluster with near-warning commands, prioritise that verified cluster count and its detailed relative timestamps over the less relevant 'zero commands matching the very last WARN instant' sentence. Preserve causal uncertainty, missing source-clock alignment and bounded history limits.
- Tests reproduce the live pattern: failed configuration vs unattempted path, unrelated device and mode isolation, subsequent successful configuration precedence, near-cluster command relevance and verified app source absence.

No new tool permission, forced model read, keyword router, Hubitat write or production Main Ask modification. V2 stays experimental and read-only.
