# HomeBrainOS v0.18.159 — Incident-first investigation accuracy

## Changes

- Investigation V2 now prioritises a source-attested command issuer whose command closely precedes an adverse state observation for the *same target* (10-minute bounded correlation), instead of automatically choosing the numerically lowest or most frequent issuer. This only chooses which stored app configuration to read; temporal correlation does **not** verify causation or physical state.
- The deterministic investigation report now recognises a subsequent Hubitat switch=off state after an issued OFF command and explicitly distinguishes this software state report from independent physical verification. When no matching report is recovered, absence remains unverified because source history can be incomplete.
- Synthetic regression fixtures cover incident-adjacent OFF versus a later ON recovery command and unrelated-device isolation.
- Existing read-only host tool gates, model permissions and confirmation requirements remain unchanged.

## Known limitations

- A successful app-configuration read with zero supported typed fields remains diagnostically incomplete.
- The cloud planner can still time out; the established host evidence fallback preserves all recovered observations but does not independently prove a root cause.
- A power/network self-disconnection mechanism requires separate topology/reachability evidence.

## Acceptance

CI validation, release assurance and Hubitat MCP AI tests must all pass before merging. Repeat the read-only Bedroom 3 Mesh investigation after deployment to verify issuer #3950 is investigated before a later button-controller recovery attempt.