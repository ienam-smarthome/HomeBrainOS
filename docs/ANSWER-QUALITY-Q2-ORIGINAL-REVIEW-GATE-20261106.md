# Q2 — private original-answer verification and per-session reviewed-pair gate

**Date:** 6 November 2026. **Scope:** offline evaluation infrastructure, not HomeBrain add-on behaviour. Production add-on version remains `0.18.427`.

## Motivation and measurement boundary

Four real local Qwen3.5:4b versus Llama3.2:3b first-answer pairs were privately captured on 4 November. The source packet fingerprints, requested model identifiers, original response digests, local checkout commit SHAs, first-attempt metadata and request timings have been preserved in `tests/fixtures/answer_quality_q2_recorded_pairs_v1.json`. Each pair had one checkout SHA, but **four different checkouts were used across the four cases**. The existing source reviews are qualitative and unblinded, not answer-bound completed human rubric records.

The next generalisable bottleneck is answer-byte **provenance**, not another lighting/MQTT/Rule Machine phrase patch. An archived answer digest is not a copy of the original answer. Do not score a reconstructed synopsis, a whitespace-altered paste, an amended response or a second model attempt.

Two previously provided verbatim user answers were independently SHA-256 checked in the private conversation without rerunning either model: Llama `aq_network_broker_vs_device_health` and Llama `aq_command_issuer_vs_reporter`. Both matched the already archived digests. This is **2 of 8 original answer text matches**; no new human grading or production-quality change follows from this integrity result. The other six original files have not been independently rehashed by this new gate. **Never commit those user answers to this public repository.**

## Implementation

`scripts/answer_quality_q2_original_reviews.py` reads original first-answer files from a **local private directory outside the checkout**, hashes their exact raw bytes, and fails closed unless each submitted baseline/candidate pair matches the archived SHA-256 values. It reuses the unchanged 40 frozen synthetic source packets and historical first-attempt metadata through `audit_recorded_pairs`. It refuses symlinks, in-checkout originals, duplicate/unknown case IDs, unexpected manifest keys, overlarge files and mismatched bytes, and avoids printing private file names or raw text even for failures.

A human-reviewed grade file is **optional**. With no reviews, output stays `not_measured`. If a separately completed and source-inspected answer-SHA-bound review is provided, the tool calls the existing `build_paired_review_report` **separately for each pair**, preserving the same-build identity gate within each case. Cross-case builds are never merged into a single same-build accuracy percentage. All five grade dimensions are reused; grades are never invented by code or inferred from word matches.

The only report identifiers are fixed case IDs and model labels, verified file counts, per-case source-review grade deltas *when supplied*, and unverified flags. Raw answers, local paths, answer digests, human pseudonyms and original manifests are not included in the output.

## Private, read-only use

The input JSON below is an **illustrative path schema only**, not real evidence. Store this file, original answer files, optional reviewed rubric JSON and report outside the repository.

```json
{
  "schema": "homebrain-answer-quality-q2-original-files.v1",
  "cases": [
    {
      "case_id": "aq_network_broker_vs_device_health",
      "baseline_file": "C:\\Users\\Example\\Private-Q2\\aq_network_broker_vs_device_health.baseline.txt",
      "candidate_file": "C:\\Users\\Example\\Private-Q2\\aq_network_broker_vs_device_health.candidate.txt"
    }
  ]
}
```

Run locally, without Cloud/model calls or live system access:

```powershell
python scripts/answer_quality_q2_original_reviews.py --files "C:\Private-Q2\original-files.json" --output "C:\Private-Q2\original-audit.json"
```

Only when a real reviewer has privately inspected **both original full answer texts**, their original frozen source packet, and completed a digest-bound `homebrain-answer-quality-paired-reviews.v1` file:

```powershell
python scripts/answer_quality_q2_original_reviews.py --files "C:\Private-Q2\original-files.json" --reviews "C:\Private-Q2\human-reviewed-pairs.json" --output "C:\Private-Q2\reviewed-pair-audit.json"
```

A review is not automatically authenticated by this command. Source packet accuracy, provider ingestion, individual model identity, first-attempt authenticity and Claude parity are **not established** by file hashes. The four different local checkout SHAs prevent pooled same-build accuracy. Only user-supplied, source-inspected, byte-bound individual grades can be reported. Missing cases remain `not_measured`.

## Tests, risks and rollback

Tests use **synthetic local files and fake grades only**, never archived private answers; they enforce mismatched-byte failures, missing original/review gaps, source checkout restrictions, symlink rejection, contradiction checks, per-session review handling across different builds and zero-review honesty. No production routing, publisher, model settings, MCP calls, Hubitat/HA/router writes, Rule Machine authoring, provider charges or version change. This is an evidence-join tool, not an accuracy improvement.

Revert this standalone script/tests/docs if it could disclose private answers, infer real rubric grades, skip original-byte checks, or combine differently built sessions. Next action: use truly available private original bytes and independent source reviews; otherwise preserve the unmeasured boundary and develop a fixed-packet cross-domain, evidence-first reasoning candidate before touching production publication.
