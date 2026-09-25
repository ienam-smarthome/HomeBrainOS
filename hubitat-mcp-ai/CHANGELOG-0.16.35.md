# Hubitat MCP AI 0.16.35

## Prefer the newest open ON boundary and keep clarification text readable

The live 0.16.34 Hallway retest exposed a causal boundary-selection bug while
Hallway Light 1 was currently ON.

The subject history contained:

```text
openActiveStart: 10:15:22
```

but the deterministic answer investigated the previous completed interval:

```text
10:02:59 -> 10:03:46
```

## Root cause

Temporal analysis correctly retained the current open ON interval separately from
completed intervals, but `boundary_event_evidence()` built its preserved
boundary set only from completed interval start/end pairs.

The latest 10:15:22 ON row therefore remained in ordinary observed history but
was omitted from `boundaryEvents`. Boundary-producer correlation could match
only the older completed ON boundary.

## Fix

0.16.35 includes `openActiveStart` in deterministic boundary-event evidence.

For:

```text
Why did Hallway Light 1 turn on?
```

when the newest ON transition is still open, authoritative provenance now
targets that newest ON boundary.

The open transition remains duration-unbounded: HomeBrain must not invent an
end time or claim that the current ON interval has ended.

## Web UI clarification separator

0.16.34 preserved causal intent correctly but used a newline before:

```text
Device clarification: use exactly Hallway Light 1.
```

The Web UI query control is a single-line input, so browsers strip that newline
and displayed:

```text
Why did hallway lights turn on?Device clarification: use exactly Hallway Light 1.
```

0.16.35 uses an explicit space:

```text
Why did hallway lights turn on? Device clarification: use exactly Hallway Light 1.
```

The backend clarification semantics are unchanged.

## Regression coverage

Tests verify that:

- `boundary_event_evidence()` preserves an exact open-active start event;
- an open ON boundary newer than a completed interval wins deterministic
  boundary-producer finalization;
- the open interval is not described as having ended;
- the Web UI emits a visible space before device clarification;
- direct control-choice behavior from 0.16.34 remains unchanged.

The existing cached-candidate-plan fallback remains unchanged and observable via
`causal_cached_candidate_plan_fallback`.
