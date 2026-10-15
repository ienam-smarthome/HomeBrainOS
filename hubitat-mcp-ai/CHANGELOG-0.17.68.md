# HomeBrain v0.17.68 — Final-response causal evidence gate

- Apply the command-clue evidence guard at the terminal final-answer boundary as a separate safeguard from synthesis validation.
- Anchor the safeguard to the original request in a request-local context variable, not potentially appended host instructions.
- Continue reviewing successful device-scoped history receipts rather than stopping at the first receipt when it does not contain the candidate.
- Correct additional contradictory absence-of-command formulations in the actual v0.17.67 failed answer.
- Register a metric for terminal corrections and replay the previous live failed answer in regression tests.

Read-only safety remains unchanged. Live verification is required, and automation topology/required diagnostic source completeness remain future work.
