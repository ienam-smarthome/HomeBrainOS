# HomeBrain 0.17.12 — Physical bridge and reactive-command causal investigation

The 0.17.11 live comparison exposed an architectural split: a configured motion sensor followed by an app-issued ON command was investigated in 8.8 seconds (one model round), while an externally reported physical ON from the Hue Bridge Pro took 37.8 seconds (six rounds) and still missed the downstream Hubitat brightness correction. The longer trace spent time resolving wrong/partial labels and querying logs for earlier long intervals instead of the explicitly requested 08:16 turn-on.

## General fixes (not limited to Bedroom 1 or Hue)

- **Stable subject resolution:** An exact, longer named device (e.g. "Bedroom 1 Light") beats its contained shorter room/group name ("Bedroom 1") in the same identity inventory, while equally specific duplicate names and fuzzy numbered collisions remain ambiguous. This restores deterministic subject-history prefetch without ungrounded broad searches.
- **Focal time selection:** A question naming HH:MM without seconds now selects an observed transition only when its clock minute is unique, optionally constrained by an explicitly named calendar day. HH:MM:SS retains second precision. Ambiguous times and wrong dates fail closed.
- **Requested event outranks long history:** Native-log windows prioritise the uniquely specified event even when it lasted only two minutes. This prevents spending the bounded log-search budget on earlier 30-minute intervals.
- **Physical causal evidence graph:** Distinguishes physical state reported by a bridge, event delivery to Hubitat app listeners, and independently timestamped controller button reports. It retains signed event order: a button event recorded 82 ms **after** ON can be a strong repeated upstream association but not a proven earlier Hubitat command or a confirmed native bridge mapping.
- **Post-ON command verification:** For a deep read-only investigation of an externally reported ON, the host gathers targeted `command-setLevel` history of the light, plus current configuration and scoped logs of the most relevant state-change listener (when the MCP gateways are available). An app-issued setLevel *after* ON is a candidate reactive brightness adjustment, not the original ON command.
- **OFF correlation separated:** The graph retains bounded motion/presence-inactive correlations with the corresponding OFF boundary without falsely identifying Hue, Aqara, or a Hubitat rule as the OFF-command source.
- **Physical one-pass sufficiency:** Like the app-command path from 0.17.11, a comprehensive physical-event investigation can now go directly to one final model synthesis **only** when it has verified the bridge report, a repeated aligned controller candidate, the relevant notified app configuration and scoped execution log, the post-ON command-history read, and checked alternative sensor evidence. A mode-history gap still requires a bounded targeted read; missing or ambiguous source classes keep dynamic MCP tool discovery.
- **Metrics:** `causal_physical_response_reads` tracks these bounded targeted reads.

## Safety and limitations

Read-only Hubitat investigation; no device/rule/settings mutations or permission/confirmation changes. Current app configuration does not prove historical behavior or the native Hue/Aqara automations. Repeated timestamps do not reveal who pressed a dimmer. An app recorded in a state event's `triggered[]` is a notified listener, not the producer of that state. The add-on still needs a live comparison after updating; no measured latency gain is claimed from unit tests.

## Example distinctions

- Light ON state reported by Hue Bridge: **observed**.
- Dimmer button 1 reported 82 ms later, with three near-aligned ON events: **strongly associated, upstream mapping unverified**.
- Hubitat app issues setLevel(45) 51 ms after ON (when recorded): **verified downstream brightness command**; not evidence it originally turned the light on.
- FP300/Aqara occupancy reports inactive shortly before OFF: **OFF-time correlation**, not independent proof that an Aqara automation issued OFF.
