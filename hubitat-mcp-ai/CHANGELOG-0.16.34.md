# Hubitat MCP AI 0.16.34

## Web UI clarification-choice intent preservation

The live 0.16.33 Hallway test exposed a front-end-only clarification bug.

The original question was:

```text
Why did hallway lights turn on?
```

HomeBrain correctly returned two choices:

```text
Hallway Light 1
Hallway Light 2
```

but tapping `Hallway Light 1` caused the Web UI to submit and display:

```text
turn on Hallway Light 1
```

The backend still resumed the stored causal clarification correctly, so the
light was not treated as a new write request. However, the visible question and
conversation history no longer represented the user's intent.

## Root cause

The Web UI choice helper used an unanchored action matcher:

```javascript
question.match(/\b(turn\s+on|turn\s+off|toggle)\b/i)
```

That matched the words `turn on` inside the causal sentence
`Why did hallway lights turn on?` and rewrote the clarification as an
imperative command.

## Fix

0.16.34 only performs the compact control rewrite when the original prompt is a
clear direct control request, including forms such as:

```text
Turn on hallway lights
Please turn off hallway lights
Can you turn on hallway lights?
```

Those still become, after selecting a device:

```text
turn on Hallway Light 1
```

Non-control questions keep the original prompt and append the exact-device
clarification:

```text
Why did hallway lights turn on?
Device clarification: use exactly Hallway Light 1.
```

This preserves causal/history intent and keeps the displayed question,
conversation history, and backend request aligned.

## Regression coverage

Tests verify that:

- direct imperative and polite control forms still preserve their action;
- action matching is anchored rather than scanning the whole question;
- the old unanchored matcher is absent;
- non-control clarifications preserve the original question and exact selected
  device;
- the existing attribute-choice behavior remains unchanged.

No causal engine, device-control, provenance, or MCP behavior changes in this
release.
