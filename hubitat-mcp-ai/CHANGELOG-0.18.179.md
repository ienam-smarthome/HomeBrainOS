# HomeBrainOS v0.18.179 — source-first incident answers without futile model rounds

## Live evidence motivating the change

The 28 October v0.18.178 causal test for Livingroom Light 2 (device
7828) recovered the correct command issuer #4020, source reporter #7790,
and two controller-selected sensors #7978 and #7778. Device 7978 had
motion=inactive at 00:14:00.481 UTC, command-off was issued by #4020 at
00:14:56.868 UTC and the switch=off report followed at 00:14:57.111 UTC.

Despite retrieving these evidence rows, the user-facing answer led with
an older competing-controller incident involving app 4129, omitted the
relevant motion transition from the short timeline, and spent 31.833
seconds generating a structured model plan after all eight permitted
reads had already executed. The overall response took 89.781 seconds.

## Architecture improvements

- New generic source-first incident summary correlates the **latest**
  reported switch transition with its exact source-time command pair,
  rather than older unrelated incidents. App identity is derived only
  from attested producer IDs and a bounded two-second same-device pair.
- The host checks explicitly configured motion sensor IDs from the
  command issuer's read-time settings, selects each sensor's latest
  event within ten minutes before the command, and computes observed
  timings without inventing a configured delay or historical rule
  decision. Missing keep-on sensor readings remain an explicit gap.
- The short user-facing report leads with that source-backed sequence.
  Its first timeline now includes the actual command, state and
  configured motion witness observations; unrelated historical
  network status and other controllers remain in full technical
  evidence rather than being presented as the main cause.
- When the normal host READ budget has been exhausted *and* this
  complete attested command/state/motion chain is in the case, the
  optional model planner is skipped. The model cannot obtain an
  additional authorised read at that point. The report records
  `source_backed_read_budget_reached`, with explicit diagnostics,
  rather than silently treating an empty model plan as success.
- If read capacity remains and source-backed configured motion
  evidence exists, model planning is permitted but bounded to seven
  seconds. Other investigations retain their normal planning budgets.
- Source case, projection, logs redaction, read authorization, V2
  write fence, production Main Ask writes and provider settings
  remain unchanged.

## Expected acceptance

For the 28 October Light 2 case, the user-facing answer should mention:
- app #4020 command-off at 00:14:56.868 UTC;
- switch=off reported at 00:14:57.111 UTC, 243 ms later;
- configured motion sensor #7978 last reported inactive at
  00:14:00.481 UTC, 56.387 seconds before the command;
- current `inactiveAction=off` setting if retrieved;
- historical rule branch and cause of the timing gap remain unverified;
- sensor #7778 keep-on history is incomplete at the incident;
- app #4020 log read failed, not necessarily empty/restart-lost.

The live log adapter still reports `mcp_tool_reported_error` for the
current log gateway; this release does not invent a workaround.

## Limits and next stage

This change addresses report relevance and futile model latency, not
the existing 20-second cold identity inventory or richer model-led
tool discovery. A command-to-reported-state pair is not independent
physical confirmation, and current configuration is not historical
runtime proof. Continue the separately gated native MCP tool-loop
migration after read-only live acceptance and provider/tool contract
tests. No Hubitat commands or automation writes are performed.
