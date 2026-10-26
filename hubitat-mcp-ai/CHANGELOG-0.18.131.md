# HomeBrainOS v0.18.131 — V2 device identity, automatically resolved

- The V2 test question alone can identify an actual Hubitat device. A fresh live Hubitat device inventory is required before any reads; deterministic whole-device-name matching returns verified numeric IDs without passing untrusted model guesses into the read loop.
- The previous mandatory device ID field is now in the **Advanced** section. An optional friendly-name override supports unusually named devices; manual numeric IDs remain a fallback.
- Ambiguous labels, non-unique identities, absent devices, and more than four targets fail closed with actionable field messages, **before** any investigation tools are called.
- The test result explicitly displays and exports the resolved device names, IDs and resolution method. No credential, token or raw inventory is included in the answer.
- V2 remains separately token gated, opt-in and read-only. Normal Ask (V1) and write routes are unchanged.

Manual testing required before production cutover; automatic name matching does not mean all natural-language pronouns or device aliases are supported.
