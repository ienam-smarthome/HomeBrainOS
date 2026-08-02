# Hubitat MCP AI 0.10.302

## Added

- Record confirmed Rule Machine verification duration at the exact deterministic verification boundary.
- Increment `mutation_verification_failures` only when a confirmed Rule Machine write does not return a verified ID and healthy result.
- Keep successful verified writes free of failure counters.
- Add focused regression coverage for verified and unverified confirmed writes.

## Safety

- Verification remains deterministic and fail-closed.
- Metrics use the existing fixed privacy-safe vocabulary.
- No rule names, payloads, device identifiers, prompts, or tool arguments become metric labels.
- Invalid queued proposals remain rejected before execution and are not counted as post-write verification failures.
