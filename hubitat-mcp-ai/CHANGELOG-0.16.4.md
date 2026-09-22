# Hubitat MCP AI 0.16.4

## Full-world host entity grounding

A live 0.16.3 test showed that host-owned target grounding could still be
bypassed on larger installations. The grounding code consumed the same bounded
semantic-world JSON sent to the model. When the planner context was trimmed for
size, a valid room could disappear before the host tried to bind the final
target.

0.16.4 separates those concerns:

- the reasoning model still receives the bounded semantic capability context;
- HomeBrain retains the complete cached identity world for host-owned entity
  grounding;
- final room/device binding uses that complete world rather than the truncated
  planner payload;
- explicit full device names continue to take precedence over room mentions;
- deterministic execution still receives only the compiled, host-grounded
  control arguments.

This fixes the observed request:

```
increase hallway brightness
```

when the model proposes `Hallway dimmer` but the complete host world contains
the real `Hallway` room with `Hallway Light 1` and `Hallway Light 2`.

## Regression coverage

Adds a production-agent regression with a deliberately oversized identity set.
The test proves that:

- the Hallway lights are absent from the bounded model context;
- the Hallway room is still present in the complete host world;
- the model may propose the wrong `Hallway dimmer` device;
- HomeBrain rewrites the final target to room `Hallway`;
- the deterministic adapter receives `adjust_level` for the room;
- `semantic_target_grounded` is emitted.
