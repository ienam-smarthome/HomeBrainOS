# Hubitat MCP AI 0.10.457

## History boundary proof hardening

Live 0.10.456 testing exposed a serious edge case in semantic device-history
reasoning. Two reads of Hallway Light 1 within about a minute produced mutually
incompatible complete totals for the same `last night` window: one deterministic
receipt reported 13h 46m while another reported 8m. The long result came from a
window-start inference that treated the first binary state row as a transition
without requiring explicit transition proof.

This release fails closed at that boundary:

- first-transition window inference now requires `isStateChange=true` (boolean or
  the equivalent string) on the first in-window binary event;
- an ordinary state report with the flag missing no longer lets HomeBrain infer
  the opposite state all the way back to the window start;
- the same explicit-transition requirement applies to post-window evidence used
  to close an otherwise empty history window;
- if the boundary is not proven, coverage remains `partial` and the duration is
  reported as a lower bound rather than manufacturing a complete total.

## Better live auditability

Temporal evidence details now expose bounded diagnostics needed to compare repeated
history reads without dumping the full event stream:

- `sourceEventCount`
- `analysisEventCount`
- `attributeInferred` when applicable
- `analyzedStateEventCount`
- the first state event inside the requested window
- the predecessor state event when one exists

These fields make it possible to see whether two runs analysed different source
rows or disagreed only on boundary interpretation.

## Faster ambiguity handling

Semantic history now resolves the requested device before reading the authoritative
Hubitat timezone. Ambiguous or missing targets therefore return their clarification
without an unnecessary `hub_get_info` call. Successful semantic history still
uses the Hubitat IANA timezone exactly as before.

## Validation focus

Regression coverage includes:

- an unmarked early `off` report cannot manufacture an almost-full-night `on`
  duration;
- explicit `isStateChange="true"` still permits valid first-transition inference;
- an unmarked post-window report cannot turn an unknown zero into a proven zero;
- mixed level/switch history produces the same temporal result whether the model
  explicitly requests `switch` or HomeBrain infers it;
- inference and source/analysis counts are visible in evidence details;
- an ambiguous semantic history target performs no timezone read.
