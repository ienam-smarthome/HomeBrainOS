# v0.18.245 — Source-first explanation after successful Historical Journal recovery

## Live failure

On 30 October 2026, v0.18.244's original HomeBrain recovered the previously missing Bathroom Light 1/2 source event timestamps: 17 source-timestamped switch observations and 23 additional collector-reception observations across Bathroom Light 1 (7818), Bathroom Light 2 (7821) and Shower Light (7807). It retrieved app-issued button OFF commands (1568, 1569), brightness commands (4013, 4014) and the 07:15 School Run mode change. But because the original Hubitat bounded light event pages still contained no switch events, the final safety fallback **overrode the natural explanation with a 60-plus-row technical ledger**. It correctly stated that the upstream ON controller was unverified, but did not explain the retrieved causal chronology.

## Architectural improvement

- The original agent continues to select investigation reads and use the Historical Journal fallback. **No separate V2 test engine returns.**
- When independently source-timestamped journal switch observations exist for at least two verified target devices, the final provenance guard presents a short, source-derived explanation and bounded timeline instead of the full technical ledger.
- Pair a matching collector-received state copy to a prior source-timestamped state only when device ID, state and a nonnegative reception lag (up to 4 s) agree. Do **not** count such copies as independent switch transitions.
- Preserve collector-only observations separately, describing their timestamps as **reception times**, not proof of actual event times. Retain connection-gap and partial-history warnings.
- Group near-simultaneous identical source-state changes across requested devices, while separately matching preceding issued OFF commands to observed OFF reports and subsequent setLevel brightness commands to already-reported ON events.
- Include hub-mode timing only if an independently read mode observation exists. A mode-triggered setLevel is not the initial ON of a light that already reported ON earlier.
- Do not claim that Home Assistant, Hue, SmartThings, Aqara or a specific sensor physically initiated an ON without contemporaneous independently verified upstream execution evidence. Do not mislabel the Hue Bridge event reporter as an external initiating controller.
- Keep the full, typed event and journal receipt set available in read-only investigation evidence, not in a duplicated user-facing timeline.

## Acceptance

Replay the actual incident's 17 source/23 collector observations: source events around 02:18, 02:52, 03:04, 03:40, 03:46, 07:12 and 07:27; two button OFF apps; 07:15 mode-based brightness adjustment; six collector-only earlier observations. Confirm that the final explanation is readable and bounded, does not silently discard Bathroom Light 1/2, and does not promote source reception to a proven physical event timestamp. In collector-only or incomplete single-source cases retain the conservative technical ledger rather than invent a cycle.

Run full Python suite, Hubitat MCP AI tests, release assurance, repository validation and add-on smoke. Installation and actual ongoing external-controller cause must still be checked live on Home Assistant.
