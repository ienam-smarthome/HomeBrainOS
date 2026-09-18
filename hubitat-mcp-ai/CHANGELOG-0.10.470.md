# Hubitat MCP AI 0.10.470

## Deterministic single-controller causal follow-up

Live validation of 0.10.469 exposed the remaining weakness in controller-first
investigation: room discovery successfully returned structured controller
`eventSourceHints`, but the model still chose to synthesize without issuing the
reserved controller-history call.

The response therefore knew that several potential controllers existed but had to
admit that no controller event history had been gathered.

0.10.470 removes that model-choice dependency.

### Host-owned controller follow-up

When an investigative room filter exposes controller candidates, HomeBrain now:

1. selects the already-ranked first controller candidate;
2. selects that candidate's first advertised suggested history attribute;
3. executes exactly one `homebrain_device_history` read host-side;
4. appends the result to current-turn evidence; and
5. immediately requests final synthesis with no further controller/sensor expansion.

This uses the same active semantic history-window context as the subject history, so
an overnight investigation keeps the controller read aligned to that requested
window.

### Why this replaces the reservation-only approach

Previous releases demonstrated both failure directions:

- 0.10.468: the model used controller hints but fanned out across four dimmers,
  reaching 6 model rounds / 20 calls / 28.8s.
- 0.10.469: the model saw the controller hints but skipped controller history
  entirely, ending after 3 model rounds / 6 calls.

The deterministic host follow-up removes both behaviours. The model no longer
decides whether or how many controller candidates to inspect after room discovery.

### Safety and scope

- only the highest-ranked structured candidate is read;
- no device names are hard-coded;
- the history attribute comes only from the candidate's structured
  `suggestedHistoryAttributes`;
- environmental sensors remain outside this controller follow-up;
- the result is still evidence, not automatic proof of who physically operated a
  control.

## Regression coverage

Tests verify that:
- only the first ranked controller candidate is selected;
- only its first suggested controller history attribute is used;
- missing label/attribute metadata yields no follow-up; and
- lower-ranked candidates are not expanded into additional reads.
