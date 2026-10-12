# HomeBrain 0.17.13 — Evidence-budget controls and trustworthy historical coverage

The live 0.17.12 Bedroom 1 investigation improved from 37.8s to 19.0s and six model rounds to two, but increased MCP/local tool calls from 21 to 40. The returned evidence showed three ON transitions closely aligned with Hue dimmer button events, plus a separately evidenced earlier ON from Maker API (HD+) app 2355. The investigation nevertheless read ten unrelated cross-room motion sensors and described button correlation with “every” light-on interval.

## Architectural improvements

- **Controller evidence stop:** A new generic, source-derived sufficiency test examines controller-to-target alignments at the *requested* state boundary and requires a repeated, unique, same-button pattern within 350 ms before stopping additional cross-room occupancy discovery. The existing room-first motion/presence checks are still performed. An equally strong competing controller, nonmatching button values, nonmatching requested time or ON/OFF transition mismatch does not qualify. This is an investigation search stop, **not** proof of native Hue binding or an automatic exclusion of unexamined alternatives.
- **Reuse positive command evidence:** When the subject's initial live history already includes an app-owned `setLevel` within five seconds *after* the ON boundary, that timestamped command is used for downstream-response analysis without repeating the 168-hour `command-setLevel` read. The graph considers a positive, source-tagged command observation sufficient; absence of such an observation still requires the targeted read before concluding command-history coverage.
- **Quantified controller coverage:** The shared causal graph now carries observed ON count, aligned distinct controller ON starts, unmatched recorded starts and any independently confirmed alternative app-command ON events. A deterministic claim guard prevents “every/all ON interval” statements from overstating the actual examined events; it only corrects relevant unqualified controller-history universal claims, retaining true bounded phrases such as “all three recent button events.” Both synthesis and final API serialization apply this contract when focal evidence is available.
- **Model-round auditability:** Fixed privacy-safe metrics now identify synthesis validation issue counts, safe localized corrections, actual extra provider-repair rounds, and broad reasons (causal coverage, causal provenance, performance, other), including failed repair. Previously a result with two model rounds did not reveal whether a substantive evidence gap or an avoidable wording repair caused the extra pass.
- **Fewer unnecessary rewrites:** A complete physical event graph is now eligible for the same evidence-localized deterministic corrections as an app-initiated graph. Safe, bounded source/provenance/coverage corrections return the corrected answer without prompting the provider a second time. Genuine timeline omissions, unresolved evidence-source conflicts and complex semantic violations still trigger normal model repair.

## Boundaries

This is a read-only reasoning, retrieval and presentation update. Existing capability/confirmation/write safety gates and MCP tool availability remain unchanged. Stopping cross-room discovery does not mean other sensors could not have been involved, and an externally observed bridge event does not identify the native Hue/Aqara automation that caused it. “Three of five observed starts” describes the bounded returned evidence; it is not proof of exhaustive historical coverage.

## Regression testing

Tests cover competing controllers and mixed button values, signed event ordering, controller budget stops, graph coverage with a different app-issued command, preservation of qualified historical wording, reuse of known post-ON brightness commands, final response contract, and categorised model repair rounds.

The actual reduction in live tool calls and end-to-end latency needs verification after installing 0.17.13.
