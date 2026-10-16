"""Read-only consistency check of lockout values in model-authored summaries.

These are claims in a response, not independently validated persisted settings.
Disagreement must be exposed, not silently resolved by choosing one number.
"""
from __future__ import annotations
import re


def lockout_claim_disagreement(message: str) -> dict | None:
    text = str(message or "")
    if "lockout" not in text.casefold():
        return None
    labels = {
        "persisted": re.compile(r"(?i)(?:persisted\s+(?:setting|value)|configured\s+(?:manual[- ]off\s+)?lockout|manual[- ]off\s+lockout[^.!?\n]{0,40}configured\s+for)\s*(?:is|:|for|of|=)?\s*\*{0,2}(\d{1,4})\s*(?:minutes?|mins?)"),
        "summary": re.compile(r"(?i)(?:summary\s+(?:paragraph|page|text)|app(?:lication)?\s+summary)[^.!?\n]{0,65}?\b(\d{1,4})\s*(?:minutes?|mins?)"),
    }
    values = {kind: int(m.group(1)) for kind, regex in labels.items() if (m := regex.search(text))}
    if len(values) != 2 or len(set(values.values())) < 2:
        return None
    return {
        "kind": "lockout_setting_summary_disagreement",
        "persisted_claim_minutes": values["persisted"],
        "summary_claim_minutes": values["summary"],
        "status": "unresolved",
    }


def annotate_lockout_disagreement(message: str) -> tuple[str, dict | None]:
    discrepancy = lockout_claim_disagreement(message)
    if discrepancy is None:
        return message, None
    return (
        message.rstrip()
        + "\n\n**Configuration disagreement:** This answer reports a persisted lockout of "
        + str(discrepancy["persisted_claim_minutes"])
        + " minutes but an app summary of "
        + str(discrepancy["summary_claim_minutes"])
        + " minutes. These figures have not been reconciled against independent persisted settings; "
          "the current remaining countdown is not proof of the configured duration.",
        discrepancy,
    )
