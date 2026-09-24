# Hubitat MCP AI 0.16.31

## Zero-model causal room/group clarification

0.16.30 fixed the important second half of the Hallway flow:

```text
Why did hallway lights turn on?
-> choose Hallway Light 1
-> deterministic causal continuation
```

The live 0.16.30 retest confirmed the selected-device step was now excellent:

```text
causal_clarification_resume: 1
model_rounds: 0
causal_native_log_reads: 0
causal_deterministic_finalization: 1
total: ~1.3 s
```

One avoidable cost remained on the first turn.

## Previous first-turn behavior

For:

```text
why did hallway lights turn on?
```

the model performed one provider round only to choose
`homebrain_device_history("hallway lights")`.

That local tool then immediately reached the existing deterministic room-kind
resolver and returned:

```text
Hallway Light 1
Hallway Light 2
```

Observed live first-turn cost:

```text
model_rounds: 1
tool_calls: 2
provider: ~1.8 s
total: ~3.0 s
```

The model contributed no useful reasoning to that ambiguity.

## Fix

0.16.31 moves only this narrow ambiguity check ahead of model routing.

For an explicit switch-causal question, HomeBrain now:

1. extracts the explicit causal subject;
2. checks the authoritative identity cache;
3. applies the existing exact room + device-kind resolver;
4. if multiple concrete devices match, returns the clarification locally;
5. records a deterministic resolver receipt;
6. preserves the original causal objective for the 0.16.30 continuation path.

For the Hallway case:

```text
hallway lights
-> exact room: Hallway
-> device kind: light
-> Hallway Light 1
-> Hallway Light 2
```

## No event read before selection

The first-turn clarification does not read device history or logs.

It only resolves identity structure. Event history is deferred until the user
selects a concrete device.

This keeps causal evidence scoped to a real subject and avoids duplicate work.

## Conservative scope

The fast path activates only when all of the following are true:

- the request is a causal investigation;
- it explicitly names an ON/OFF switch transition;
- the subject can be extracted by a narrow deterministic grammar;
- the subject is an exact room + device-kind reference;
- authoritative identity metadata resolves that phrase to more than one device.

Exact device questions are not intercepted.

Broader causal language that does not meet this contract continues through the
existing reasoning path.

## Expected Hallway first-turn result

```text
message:
  I could not resolve **hallway lights** uniquely.
  Possible matches: Hallway Light 1 or Hallway Light 2.

choices:
  - Hallway Light 1
  - Hallway Light 2

model_rounds: 0
tool_calls: 0
causal_group_clarification: 1
device_resolution_ambiguous: 1
```

The technical evidence contains one local
`homebrain_resolve_device` receipt backed by the authoritative identity world.

## Metrics

Adds:

```text
causal_group_clarification
```

This distinguishes the initial zero-model group clarification from
`causal_clarification_resume`, which records the selected-device continuation.

## Regression coverage

0.16.31 adds tests proving that:

- `why did hallway lights turn on?` extracts `hallway lights`;
- Hallway Light 1 and Hallway Light 2 are found from exact room-kind identity;
- Kitchen Light and Hallway Meter are excluded;
- the provider receives zero requests;
- MCP receives zero calls when identity cache is already available;
- model rounds remain zero;
- tool calls remain zero;
- the same two choices are returned;
- the original causal objective is stored for the next selection;
- one deterministic resolver evidence receipt is recorded;
- an exact device question such as
  `Why did Hallway Light 1 turn on?` is not intercepted by this group fast path.

## Scope

0.16.30 causal clarification continuation and triggered-listener guards are
unchanged.
