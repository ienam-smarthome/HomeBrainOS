# Hubitat MCP AI 0.10.459

## Deterministic zero/unverified history answers

Live 0.10.458 validation showed that the history evidence layer was conservative,
but the final answer could still overstate absence using wording that did not match
the existing serializer regexes. In the observed Hallway Light 1 response, the
evidence correctly reported:

- zero bounded intervals;
- partial coverage;
- an unverified device-event stream;
- no known window-start boundary;
- no mathematical lower bound.

The model nevertheless said there was "no record of it being on" and that all
recorded activity occurred later in the morning.

0.10.459 removes that wording dependency. When the current turn contains exactly
one successful `homebrain_device_history` receipt with:

- `intervalCount == 0`; and
- unverified history-source integrity,

the API serializer emits the deterministic uncertainty statement directly. It no
longer tries to enumerate every possible English way the model might phrase an
absence conclusion.

The deterministic answer states that no bounded active interval was established
from the recorded device-event rows and that the unverified stream does not prove
the device stayed inactive throughout the requested window.

## Scope

This override is intentionally narrow:

- non-zero unverified history still goes through the normal synthesis and duration
  reliability guards;
- verified zero history is not rewritten by this path;
- multiple history receipts are not collapsed into one deterministic zero answer;
- no new question-specific routing or device-specific rules are added.

## Regression coverage

Tests cover the exact live wording that bypassed 0.10.458, a semantically equivalent
absence claim with no known regex phrase, non-zero unverified history, and verified
zero history.
