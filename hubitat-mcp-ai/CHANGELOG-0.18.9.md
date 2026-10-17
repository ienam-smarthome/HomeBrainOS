# 0.18.9 — Model-driven Groovy source workbench

- Evidence from the live 0.18.8 app 4019 investigation showed five 64k source reads at overlapping 25k offsets, collectively reaching only character 164,000 of 186,457; source existed, but full coverage was not proven.
- Prefer a single **AI-selected** `homebrain_read_groovy_source` operation for a Groovy implementation question. This operation remains an evidence tool; the language model, not a canned source-specific answer, remains responsible for interpreting the code and testing competing hypotheses.
- Add an optional `symbols` list (up to 12 names) selected by the model from the user's objective. Produce bounded line-numbered code snippets at relevant declaration, use and update sites; preserve a source hash and explicitly report unmatched symbols.
- Fetch full source using sequential, nonoverlapping source offsets with requested 48,000-character pages. Four pages can cover the observed 186,457-character code body if the MCP gateway honours `length`. Refuse full-coverage claims for incomplete/gapped data.
- Count raw source retrieval as such even when no requested symbols match; lack of a hit in a partial source is not evidence of absence.
- Keep the same read-only schema/identity verification, user-controlled paid model authorisation and budget safeguards. No automatic paid escalation and no live Hubitat changes.
- Tests cover an arbitrary 186,457-character Groovy app (not just Livingroom 4019), full four-page coverage, custom model-selected identifiers, input validation, no-match retrieval and prior overlapping-chunk behaviour.

The CI suite verifies this tool behaviour with simulated MCP responses; it does not establish that the live Home Assistant add-on is updated. Test on free Gemma first.
