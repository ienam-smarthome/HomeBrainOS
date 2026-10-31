# HomeBrainOS v0.18.296 — Stage 6.1: source semantics and stopping review

This is a corrective **evaluation-contract** release, not a new production publisher or a change to any live automation.

## Reproduced user failure

The Stage 6 fictional delayed OFF report test chose S2 and S3 but stopped before reading the application command source S1. Two of its sentences were labelled `device_telemetry` even though their underlying device-source timestamp events E2 and E3 are typed `state_report`. The field values were supported, but the evidence-provenance labels were not. Stage 6's old UI presented both as "unsupported citation," inviting confusion between source-type mismatches and false factual content.

## Corrections

### 1. Source semantics: observation is not verified physical telemetry
- Device-source timestamps **inside a state report** do not turn the record into independently authenticated hardware telemetry.
- Real device telemetry requires a dedicated `device_telemetry` event with `independent_device_packet: true`. No automatic type coercion or special-case acceptance for the clock-conflict fixture.
- A source-type mismatch is now a distinct result (`source_type_mismatch`). It does NOT automatically prove that the descriptive fact is false.

### 2. Independent, exact source-field atoms (v2)
- Stage 6 final answers request `homebrain-stage6-answer.v2`, with 1–7 sentences, each with a typed source label, cited record IDs and up to four precise field-value assertions `{record_id,field,value}`.
- The host validates cited IDs, allowed factual fields, JSON primitive values, duplicates and exact source field/value equality (including types) independently of the model.
- A correct atom with an incorrect source-type label is separately visible from an actual mismatch in a claimed source time, state or command value.
- Old v1 answers remain parseable for offline review/regression but have **zero verified atoms** and are never labelled as fully proven.
- **Important:** the model authors both its sentences and its atoms. Checking declared atoms is NOT complete, independent semantic interpretation of prose. A model can omit an implication, mislabel a sentence or describe real-world physical outcomes without supporting proof. Every answer continues to show `prose_semantics_fully_verified: false` and `publisher_approval: false`.

### 3. Read/stop policy without exposing benchmark answers
- Before each STOP decision, Gemma is explicitly asked to reconsider unread command, independent state/timestamp, actuator acknowledgement and competing-issuer sources against the user's original question.
- A stopped investigation retains its model-authored stop rationale. The host separately reports whether important hidden reference sources remain unread; it **does not silently reveal or auto-read them**, which would inflate model discovery scores.
- This is a *soft stopping policy*, not proof that every premature stop is prevented. The next real cloud test measures whether it actually helps.

### 4. Mobile UI and safety
- Separate displays for source-type label mismatches, other unmatched types, exactly matched/mismatched source values and the model's stop reason.
- Uses the same configured primary Ollama Cloud account with up to four explicitly consented requests per run, same cooldown/hourly limit, zero live MCP tools and no retries.
- No live Hubitat/Home Assistant reads or writes, no credential changes, no production reasoning/publisher activation and no GitHub Actions cloud spend.
- All new tests use mocked cloud responses. Reproduce E2/E3 report-type mismatch, confirm the supported factual atom values, reject false timestamps, ensure unknown claims/ID duplicates fail, verify early-stop detection and guard against hidden reference-label leakage.

## Recommended real follow-up

Update the **Hubitat MCP AI** add-on to v0.18.296 and run the Stage 6 **Delayed OFF report versus device time** synthetic test once. Inspect **source-type mismatches**, **source-value atom matches**, **which sources were selected** and the reason for stopping. A genuinely improved result would inspect the application command-history source S1 and correctly label E2/E3 as state reports without implying confirmed physical operation. Each click may consume up to four Ollama Cloud requests from the existing account.

The evaluation remains incomplete until independent full-prose source-bound human review and more challenging, adversarial test cases. This release deliberately does not replace the production publisher.

Rollback: revert Stage 6.1 and restore v0.18.295.
