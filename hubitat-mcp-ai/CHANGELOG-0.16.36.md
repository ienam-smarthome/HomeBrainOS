# Hubitat MCP AI 0.16.36

## Concise causal answers

The live Hallway investigations proved that HomeBrain's deterministic causal
reasoning was materially more careful than a short model-generated answer, but
the main response had become too long to scan on a phone.

The goal of 0.16.36 is therefore:

```text
Claude-length presentation
+
HomeBrain-level evidence discipline
```

## Main-answer format

Direct command provenance is now presented as a compact cause-first answer:

```text
**Cause:** 05. Maker API - HD+ issued the ON command for Hallway Light 1
at 12:38:03 PM; the device reported ON 229 ms later.
- **Status:** The current ON interval is still open.
- **Note:** The Hubitat producer identifies the app/action that issued the
  command, not the person who initiated it.
```

For an externally reported physical/Matter transition without an aligned
Hubitat command producer, the normal answer is reduced to the useful evidence:

```text
**Main finding:** Hubitat has no direct command producer for this ON
transition. Hallway Light 1 reported ON via Matter Hue Bridge Pro.
- **Reporting path:** Hue carried the event into Hubitat; it does not prove
  the exact initiating action.
- **Downstream only:** listener apps reacted to the event; they are not proven
  initiators.
- **Motion/presence:** concise N/N correlation summary.
- **Shared path:** sensors sharing Matter Aqara M3 are not independent
  confirmations.
- **Limit:** timing correlation does not prove the exact automation/action.
```

## What moved out of the main answer

The following remain available in the structured evidence / Technical Details:

- individual sensor timing deltas;
- every controller candidate and non-match;
- repeated upstream-ordering paragraphs;
- per-OFF-boundary inactive-edge timing;
- detailed downstream level-recovery sequences;
- full bounded correlation payloads and producer metadata.

No evidence is discarded; it is only no longer repeated in the user-facing
answer.

## Safety / attribution behavior is unchanged

0.16.36 does not adopt the stronger causal wording sometimes produced by
general-purpose models.

In particular:

- `triggered[]` apps remain downstream listeners unless independent producer
  evidence proves otherwise;
- Matter Hue Bridge Pro remains a reporting path when no aligned command
  producer exists;
- FP300 / Soft Sensor timing remains correlation rather than direct causal
  proof;
- sensors sharing Matter Aqara M3 are not treated as independent confirmations;
- direct Hubitat command `producedBy` metadata still outranks timing-only
  correlation.

## Scope

This is a presentation-only release. Tool selection, evidence collection,
attribution thresholds, deterministic finalization, cache fallback behavior,
and model routing are unchanged.
