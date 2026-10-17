# 0.18.8 — Installed Groovy source retrieval and evidence integrity

- Read Hubitat Groovy source through the verified `hub_get_source` leaf using `{id: codeId, type: "app", offset, length}`, not the installed-app instance ID or unsupported `codeId` parameter.
- Resolve instance-to-source linkage from app metadata, including `appTypeId` only on a row whose instance ID matches. Check installed-app inventory when configuration metadata omits that linkage.
- Retrieve bounded sequential source chunks (up to 16 calls and 250,000 characters) with no skipped offsets. Source completeness requires contiguous spans and an authoritative total length, never a sum of disjoint response sizes.
- Record safe direct `hub_get_source` evidence from actual raw returned text, including offset/length/source-ID metadata without storing Groovy text in receipts. Also record explicit source completeness for the local source wrapper.
- Use direct and local Groovy-source evidence to assess source-code objectives; distinguish partial text from verified full-source coverage and avoid incorrectly reporting that no source was retrieved.
- Reinforce the general investigative model instruction: do not conflate unrelated variables and units; follow declarations, saved settings, runtime getter and state writes; do not diagnose a code bug or recommend editing settings without sufficient source evidence.
- Add tests reproducing real October 17 MCP source arguments, appTypeId identity, missing source, offset gaps, sequential pagination, evidence privacy and cross-route completion.

CI validation does not confirm the live source endpoint returns an entire implementation; verify with runtime testing. Existing Hubitat device write permissions, confirmations and paid-model budget remain unchanged.
