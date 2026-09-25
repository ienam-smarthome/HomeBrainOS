# Hubitat MCP AI 0.16.37

## Fix: keep causal provenance on the requested transition

A live 0.16.36 Hallway test exposed a correctness bug after the new concise
presentation shipped.

The final answer said:

```text
Cause: 05. Maker API - HD+ issued ON at 12:38:03.
Run: 49 seconds.
```

but the newest Hallway Light 1 transition in the same request was:

```text
13:14:40 ON -> 13:15:18 OFF (39 seconds)
```

The bounded secondary correlation correctly used the 13:14:40 boundary, so the
response was mixing two different causal intervals.

## Root cause

The initial causal subject prefetch selected the newest transition correctly.

Because its state boundary was reported through Matter Hue Bridge Pro and had no
aligned direct command, HomeBrain entered the bounded reporting-source path.
That secondary pass intentionally fetched a wider subject event page.

The wider page added an older 12:38 Maker API command-backed interval to the
current-turn evidence. During deterministic finalization,
`render_command_producer_summary()` re-ran command correlation across the
expanded evidence and promoted the older direct command merely because it was
the newest command-backed interval.

That violated the focal-transition contract: stronger provenance from an older
event must not answer a question about a newer event.

## 0.16.37 behavior

HomeBrain now establishes the newest observed boundary for the requested
transition and carries that boundary into direct-command sufficiency checks.

A command producer can become the headline cause only when its state boundary
matches that focal boundary.

Therefore:

- an older Maker API command can no longer hijack a newer Matter/Hue event;
- the reporting-source answer remains focused on the newest transition when the
  newest transition has no aligned command;
- direct command provenance still outranks timing correlation when the command
  aligns with the exact requested boundary.

## Short-interval improvement

Direct command correlation no longer discards intervals merely because they are
shorter than the generic five-minute causal-timeline materiality threshold.

That threshold is useful for weaker contextual reasoning, but authoritative
`command-on` / `command-off` producer metadata is strong evidence even for a
39-second or 49-second run.

The new regression coverage verifies both directions:

1. older 12:38 Maker API command + newer 13:14 Matter/Hue transition -> old
   command is rejected for the newer question;
2. direct command aligned with the newest 39-second transition -> command
   remains eligible and is reported as the cause.

## Scope

No change to device resolution, causal clarification, secondary candidate
selection, correlation windows, model routing, or concise 0.16.36 presentation.
