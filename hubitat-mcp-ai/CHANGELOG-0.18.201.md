# HomeBrainOS v0.18.201 — General structured claim validation and publication

## Motivation

Native Investigation V2 previously allowed arbitrary model prose for most incident types, with a special source-authoritative gate for generic excessive hub-load warnings. Although v0.18.200 introduced source-backed factual receipts for several evidence classes, it did not independently validate the model's final prose. This permitted unsupported causal claims outside the one narrow warning class.

## What changes

1. **Host-controlled claim vocabulary.** Source-backed facts are built directly from previously authorised, projected MCP read receipts across scoped device states, warning method/duration observations, device command issuers, static source structure, app metadata, and hub metrics. Candidate claim IDs are offered back to the model to select; never authorise additional MCP actions.
2. **Structured claim protocol.** A final response may nominate observed fact IDs or two-fact numerical comparisons (greater-than, less-than, equal-to). The validator resolves both operands, actual values and matching metric/units from host evidence. Incompatible, contradictory, unverifiable, negative-absence and causal assertions are rejected. Free-text conclusions and model-supplied statement fields cannot override the source.
3. **Fail-closed publication.** The host, not the model, renders every accepted finding with read receipts. Unstructured prose, unknown claim IDs, unsupported operators or malformed envelopes are not published; the host generates bounded source facts instead. Missing data are never interpreted as a verified absence. The previous source-bound unattributed-incident report remains independently host-authoritative for compatibility.
4. **Explicit diagnostics.** `structured_claim_catalog` and `claim_publication` show accepted/rejected proposed facts, source reads, publication fallback and `model_prose_published=false`. All Native V2 read permissions, tool selection and Main Ask isolation remain unchanged.
5. **No source-code or private data exposure.** Unapproved device fields, free-form event text, speech, arbitrary source content and credentials are excluded from canonical verified facts.

## Scope and honest limitations

This is a **general fail-closed typed proof gate**, not a magic semantic oracle for unrestricted natural language. It can verify only claims expressible with approved source-backed predicates; everything else is withheld. Numeric comparisons are explicitly described as comparisons of returned measurements, not proof of simultaneous readings. No internal cause is verified solely by static source or temporal event association. More typed predicates, temporal reasoning and independently attested runtime evidence can be added without weakening the publication boundary.

## Live acceptance

Update and restart experimental V2, then compare an incident question and a device status comparison. Check whether model selects valid IDs without extra synthesis overhead, which claims are published, whether unstructured claims are blocked, and whether outputs remain useful. Do not infer live performance from CI alone.

No Hubitat writes, no Main Ask changes. Full Python suite and all release CI workflows required before merge.
