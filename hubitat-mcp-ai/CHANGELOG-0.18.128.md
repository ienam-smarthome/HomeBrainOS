# HomeBrainOS 0.18.128 — guarded interactive V2 testing

- Adds a **separate browser test panel** at `/v2-test` and a dedicated `POST /api/v2/test` endpoint. Both are disabled by default.
- Requires the operator to enable `investigation_v2_testing_enabled`, set a secret `investigation_v2_test_token` of at least 16 characters, and supply the token plus `explicit_opt_in: true` with every run. The secret is not embedded in the page or persisted in local browser storage.
- Validates one to four user-supplied device IDs against a freshly fetched authoritative Hubitat device list. They are *not* inferred from the question or granted by a model.
- Runs the isolated read-only V2 model planner, MCP read loop, atomic source-claim verifier and optional source-linked narrative; returns captured answer, causal caveats, verification flags, and an honest replay scorecard.
- Allows optional pasted V1 and Claude answers for literal command-timestamp comparison only; **not** semantic/causal correctness scores.
- Advertises trusted verified target IDs to the model. Separately fixes a budgeting defect where already-gathered trusted case receipts could prematurely exhaust a new V2 test's read budget.
- Keeps normal Ask and V1 execution paths, Hubitat writes, automation configuration and default routing unchanged.

## Usage

1. In Home Assistant add-on configuration, enable `investigation_v2_testing_enabled` and set `investigation_v2_test_token` to a long random secret (at least 16 characters).
2. Restart the add-on. From the HomeBrain page, open **Investigation V2 Test**.
3. Enter the secret, the investigation question and one to four **actual Hubitat device IDs** (e.g. `7805` for the living-room light). Run the test.
4. Review source coverage, the model's candidate hypotheses and command/state distinction; optionally paste separately captured normal HomeBrain V1 and Claude answers.
5. Disable the test option after testing. The test endpoint is designed for Home Assistant ingress; avoid exposing the optional direct port to untrusted clients.

An enabled endpoint alone is not a tested live hub result. V2 is still **not** the production answer engine. Tests do not modify Hubitat, but may incur configured model-provider charges.
