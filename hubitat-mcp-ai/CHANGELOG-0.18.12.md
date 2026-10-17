# 0.18.12 — Verified Java UTF-16 source offsets and gateway read-envelope recovery

## Live problem
On installed 0.18.11, a read-only investigation of installed app 4019 (code ID 1453) retrieved only 56,000 of 186,457 source-offset units. A 48,000-unit page could contain 47,999 Python Unicode code points and advertise `nextOffset` 48,000 units later; shrinking to 8,000 temporarily recovered one page but then stopped again. The agent also emitted source-read gateway payloads wrapped entirely under `args`, receiving capability listings rather than code.

## Improvement
- Verify source offsets against **both** Python Unicode code points and Java/Groovy UTF-16 code units. An astral character counts as two UTF-16 units; only an observed offset matching a consistent unit convention is accepted.
- Preserve original fail-closed behavior for unexplained offset drift, inconsistent unit conventions, source-version or identity changes, and replacement/unpaired Unicode fragments. No missing characters or server offset gaps are skipped.
- Determine complete source coverage using independently verified offset units, separate from Python display character count; update direct raw-source evidence receipts so verified coverage never incorrectly treats legitimate UTF-16 pages as gaps or an unexplained mismatch as complete text.
- Normalize model-produced, entire-envelope-under-`args` requests only for explicitly allowlisted read gateway leaves. Write gateways and unknown operations are unchanged. Preserve the earlier same-leaf nested normalization.
- Continue distinguishing retrieved source evidence, complete implementation retrieval and method-body evidence. A valid full code read is not automatically a proof of runtime behavior.

## Safety
Read-only source retrieval and generic gateway normalization only. No Hubitat device/automation settings, existing safety approvals or Ollama paid-model budget are changed. No source-specific answer is hardcoded.

## Tests
Regress a 186,457-unit Java UTF-16 source with an emoji inside a 48,000-unit page, successful four-page contiguous retrieval, unchanged fail-closed truncated-text behavior, the live wrong read-envelope structure, read/write separation and safe source receipt counts.

## Live validation
GitHub CI verifies regression contracts. A Home Assistant add-on update and actual Hubitat code read remain necessary to confirm end-to-end runtime behavior.
