# Hubitat MCP AI 0.16.47

## Universal subject command-producer fast path

The 0.16.46 Microwave live retest showed that the correct cause was already
present in Hubitat's authoritative device event history:

- `command-on` for `Microwave (MQTT)`;
- producer `Appliance: Microwave ON/OFF`;
- command timestamp about 75 ms before the switch=on boundary.

HomeBrain still missed it because the user's short name `Microwave` did not
activate deterministic causal-subject prefetch for the canonical label
`Microwave (MQTT)`. The model-routed history call therefore read switch state
without the private command-provenance flags and expanded into weaker evidence.

0.16.47 closes both paths.

### What changed

- trailing parenthetical source/transport qualifiers such as `(MQTT)` are now
  deterministic aliases during explicit switch-causal subject matching;
- alias matching remains fail-closed when more than one identity has the same
  best score;
- `Why did Microwave turn on?` can therefore resolve directly to
  `Microwave (MQTT)` before the first provider round;
- deterministic subject history continues to fetch only the requested
  `command-on` or `command-off` stream in parallel with switch history;
- as a safety net, a model-resolved `homebrain_device_history` call for the
  explicitly named causal subject is host-enriched with:
  - `attribute=switch`;
  - command provenance enabled;
  - the requested ON/OFF transition;
  - bounded correlation history;
- after any resolved causal subject history, aligned command-producer metadata
  is checked before native logs, room/controller/sensor correlation, location
  evidence, or app navigation;
- when direct command producer evidence exists and deterministic finalization is
  enabled, HomeBrain returns immediately.

### Expected Microwave proof

For the 21:12:06 run captured in Hubitat device events:

- `Appliance: Microwave ON/OFF` issued `command-on` at about
  21:12:06.394;
- `Microwave (MQTT)` reported ON at about 21:12:06.469;
- command-to-state delay is about 75 ms.

The expected answer is therefore a concise deterministic **Cause** result naming
`Appliance: Microwave ON/OFF`, with no native-log sweep and no model round.

### Evidence boundary

A Hubitat command event with `producedBy` proves which app/action issued the
device command. It does not, by itself, prove which trigger caused that app to
run or identify a person. Rule configuration or aligned trigger-event evidence
is still required for a stronger trigger-chain statement.
