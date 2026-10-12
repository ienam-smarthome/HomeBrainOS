# 0.17.3 — Short answers that name the lighting rule and trigger

HomeBrain's deterministic causal response previously returned command-semantics paragraphs, elapsed-millisecond proofs and generic warnings instead of answering what caused an activation. This was especially visible for Bathroom Light 1 at 07:08:06 on 12 October 2026.

## Answer policy

- Lead with the observed light, local time, brightness and exact command-producing **app/rule with Hubitat ID**, in a plain sentence.
- Identify **what triggered the app/rule**: retained, timestamp-scoped app logs can explicitly verify the trigger; a configured occupancy sensor with a matching event **before** the switch transition can be described as the *likely* trigger. A sensor event reported after the light changed remains correlation, never a proven initiating event.
- If no trigger is established, say so once in ordinary English. Never invent a person, occupancy event, input or rule condition.
- Optionally include relevant later brightness adjustments and the observed OFF time, without treating another `setLevel` during an existing ON interval as a new switch-on.
- Strip transient ON/OFF and motion-active/idle decorations from an application's displayed name while retaining its app ID. Status labels can change between the command time and investigation time.
- Omit audit boilerplate (command semantics, unbounded-event cautions, command-to-switch milliseconds, trigger-disclaimer lists) from the user-facing answer. Technical evidence remains available in structured request receipts.
- Keep the causal source reads bounded and read-only. Remove an unnecessary current sensor-health read used only for verbose output.

## Regression coverage

Tests cover an actual light-command history shape, dynamic `Lights Off, Motion Idle` producer names, pre/post-transition occupancy reports, explicit app execution trigger logs, absence of trigger evidence, and simple user-facing wording.
