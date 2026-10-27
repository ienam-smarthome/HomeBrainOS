# HomeBrainOS v0.18.163 — Compact causal planning and source identity closure

## Live evidence from v0.18.162

Two read-only Bedroom 3 Mesh investigations on 27 October returned identical
source events, including the 12 October 01:30:01 BST OFF command from
event-attested source 3950, switch=off ~0.17s later, and
healthStatus=offline at 01:33:46 BST. Current stored controller settings
reference device 7103. Source 3950 does not appear as a named entry in the
current application inventory; a different automation named
"Power saving: bedroom 3 mesh" appears as 3996, but the parent/child
relationship is NOT verified.

Cold V2 duration: 35.788s with 18.362s identity inventory; repeat within
the verified TTL: 16.073s with 48ms inventory and no Hubitat pages. Both
runs still timed out after the 15s model advisory budget, with 10,307
characters of prompt, 40 source case records and 4 successful MCP reads.

## Architectural improvements

1. **Bounded, discriminating model context.** Previously all energy/voltage
   and lastSeen telemetry within 15 minutes of a command was forwarded to
   the model. Retain every material command, switch, health/network change,
   independent observation, and stored app setting; sample other telemetry
   by event kind/target using first, last and nearest before/after.
   The canonical source case, coverage and technical report remain lossless.
2. **Small model planning contract.** Shorten the system prompt and requested
   response example. Ask for at most two hypotheses and one new useful read,
   subject to unchanged host schema, known-ID and READ-only gates.
   No new model privileges, command execution or permissions.
3. **Consistent live read schema.** A gateway's model-facing nested tool
   enumeration is filtered to the reviewed read operations, instead of
   accidentally advertising unsafe/unprojected operation names alongside
   a restricted operations list. Host validation continues independently.
4. **Source uncertainty reported accurately.** A completed current app
   catalogue that does not name an event-attested issuer is described as
   unresolved; a successful stored-app configuration read does not invent
   an app name, historical parent, or deletion. The report no longer
   repeats the same incident-linked OFF command as "Another OFF".
5. **Adversarial regression fixtures** verify compactness, retention of
   all material event IDs, unchanged source case, read-enum consistency,
   current-name ambiguity, read-only planning and no duplicate OFF claims.

## Known limits

- A provider can still time out on a smaller prompt. This release changes
  context and decision structure but does not claim to cure cloud latency or
  prove causal physical networking dependencies.
- Source 3950 vs current automation 3996 is not resolved by name similarity.
- Cache speedup applies only to a recent complete, generation-valid
  identity inventory, not every cold request.
- No real device or automation writes were performed.
- Command acknowledgements, reported switch changes and independently
  verified hardware state remain distinct evidence categories.

## Live acceptance

Deploy v0.18.163 and repeat the same dated read-only question. Compare the
planning input_chars, planning outcome, elapsed_ms, source sequence and
controller name explanation against the v0.18.162 captures. Do not treat a
provider timeout or insufficient source coverage as proof of no cause.
