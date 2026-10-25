# HomeBrainOS 0.18.112 — AI-interpreted investigation scope and concise answers

## Reproduced problem
Live v0.18.111 tests show Ask working and successful device-state reads, but a
read-only Livingroom Light 1 root-cause investigation could finish as a list
of seventeen room devices, without inspecting the controlling app or timer
logic. This is objective drift: a successful inventory read does not answer
a causal question.

## Changes
- Expand one **bounded no-tools AI interpretation** to open-ended investigative
  questions, instead of limiting eligibility to a fixed collection of
  routing keyword clusters. Explicit event-clock investigations retain
  existing evidence-first paths.
- Carry the request-scoped AI-selected objective, target and purpose into
  the model-led read-only investigation instructions and remind the
  model that inventory is context, not causal proof.
- Prevent the legacy deterministic room-inventory presenter from short-
  circuiting any AI-interpreted investigation, while retaining that
  shortcut for ordinary non-investigative inventory questions.
- Keep **Investigation completeness**, unchecked source classes, and history
  integrity warnings in the existing structured Technical JSON under
  `investigation_coverage`. Do not append that internal status to the
  visible answer. Partial/unresolved statuses and raw evidence still
  remain available in Technical details.
- Do not add keyword-based routing, widen write permissions or change Hubitat.

## Live acceptance
1. Ask whether Livingroom Light 1 is OFF; expect a sourced short answer.
2. Ask when it last switched; expect a real observed event and only
   relevant limitations in technical details.
3. Ask *why* it sometimes stays ON and request the actual controlling
   automation, sensors and inactivity timers. The reply should not
   degrade into a room device list; relevant app configuration, Groovy
   source if required, event activity and unsupported assertions should
   be distinguished. A complete root cause remains unverified until
   supported by actual Hubitat evidence.
