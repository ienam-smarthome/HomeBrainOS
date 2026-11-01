# HomeBrainOS v0.18.305 — Stage 7.3: source-value declaration coverage is distinct from factual support

## Actual user test

The user's post-v0.18.304 Stage 6 fictional "Two apps issue competing commands" trial confirmed:
- **3/3 reference-relevant sources selected**, none irrelevant.
- **Complete question/value planning review**, zero ranking inconsistencies.
- **Four real Ollama Cloud requests** on the configured existing account.
- Final answer rejected: `atomic_assertion_count_invalid`. No final prose was displayed; source selection was preserved by the earlier Stage 6.6 diagnostics.

This single old error covered two materially different conditions: `atoms=[]` for a non-relational sentence, or a malformed/excessive list of source-value assertions. The screenshot did not distinguish which occurred. No inference about the content or accuracy of the rejected prose can be made.

## Design distinction

The model writes the **natural-language statement** and separately declares up to four exact atomic field/value assertions. Requiring at least one atom in every single non-relational sentence made the entire paid investigation fail even if the sentence was a careful negative or uncertainty statement that could not be represented by a direct positive field value. But simply treating missing atoms as verified would defeat the evidence-safety architecture.

The updated evaluator draws an explicit boundary:
- `atoms=[]` on an ordinary sourced sentence is **accepted as missing structured source-value coverage**, not as proof, fact-checking or production publication approval.
- `source_value_atom_coverage: missing_declared_atoms_unverified` is returned for that sentence; the run-level count `sentences_missing_declared_source_value_atoms` increases, and `declared_source_value_coverage_complete` remains false. Mobile UI displays that deficit prominently.
- A pure relation such as `competing_commands` or `time_order_conflict` can legitimately have `atoms=[]` because its evidence consists of **structural comparison of multiple records**. The existing typed host proof still checks that relation. No imaginary atomic facts are needed, and `source_value_atom_coverage: not_applicable_relation_host_proof` is explicit. Correct relation source structure **still cannot certify every implication of its prose**.
- A list with **more than four** atoms, a non-list payload, unexpected fields, uncited IDs, invalid value types and duplicates still causes a hard validation failure. Separate safe categories identify `atomic_assertion_count_exceeds_limit` versus `atomic_assertion_list_not_array`.
- A declared atom with an incorrect factually recorded value remains `source_value_atoms_mismatched`, not verified. The benchmark was never a production permission gate and does not approve the explanation.
- **High-risk claims** of unique cause, physical actuation or global absence remain unsupported by the synthetic host proof even if their atoms are correct or empty. `publisher_approval=false` and `prose_semantics_fully_verified=false` are unchanged.

## Model instructions

The final explanation prompt preserves the natural answer and direct-question requirement, and asks for up to four truthful source-value atoms per sentence **where safely possible**. If there is no safely extractable source value, it must emit `atoms=[]`, which will be **reported as incomplete**, not falsely treated as supported. The instruction does not request any model retry or additional Ollama request.

## Safety and test coverage

CI tests use only constructed fictional events and fake cloud clients. Regress missing-source-value declarations, relations with no atoms, mismatched field values, high-risk causality/global negatives, oversized and malformed arrays, duplicate/unknown IDs, zero retries and four-call limit. The Stage 7 independent human review packet remains available on a structurally accepted response, but all sentences still require independent semantic review.

The experimental UI is a **review tool**: an unverified draft may be displayed clearly as such. This does not alter, bypass or enable HomeBrainOS's production publication gate.

**No live Hubitat or Home Assistant access, no automation/device changes, no credentials or paid inference used by CI, no model/router/publisher changes beyond the synthetic test prompt.**

## Manual follow-up

After installing **v0.18.305**, run **Stage 6 → Two apps issue competing commands** once, with the existing explicit consent for up to four Ollama Cloud requests. If the answer completes, inspect **Declared atom coverage**, **Other unsupported source types (high risk)**, and the new Stage 7.2 direct-question review. If it still fails, capture the precise sanitized error category. A successful benchmark response must not be mistaken for independently verified prose.

Rollback: revert the change and restore v0.18.304.
