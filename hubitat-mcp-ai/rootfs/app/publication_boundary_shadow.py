"""Privacy-minimal observation of the generic answer publication boundary.

This is *not* a claim validator. The incoming outcome message may already be
synthesised, rewritten or repaired before shared completion. We record only
whether the host replaced it with an evidence-typed report, without retaining
user text, claims, identities, device data, hashes or timestamps. No tools,
network, model calls, writes, or publication policy changes.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "homebrain-publication-boundary-shadow.v1"
STRATEGY = "typed_target_history"


def _size_bucket(value: Any) -> str:
    """Small cardinality, bounded aggregate; not an answer excerpt."""
    if not isinstance(value, str) or not value.strip():
        return "empty"
    count = len(re.findall(r"\S+", value))
    if count <= 50:
        return "1-50"
    if count <= 150:
        return "51-150"
    if count <= 300:
        return "151-300"
    return "over-300"


def observe_publication_boundary(
    incoming: Any,
    published: Any,
    *,
    strategy: str = STRATEGY,
) -> dict[str, Any]:
    """Exposes ungraded shape-only metrics, never raw model/user text.

    Only a closed set of source-grounded publication strategies can be
    observed, so callers cannot use this object to echo private data.
    """
    if strategy != STRATEGY:
        raise ValueError("unknown publication strategy")
    return {
        "schema": SCHEMA,
        "strategy": STRATEGY,
        "incomingMessagePresent": bool(
            isinstance(incoming, str) and incoming.strip()
        ),
        "incomingSizeBucket": _size_bucket(incoming),
        "publishedSizeBucket": _size_bucket(published),
        "replacementPerformed": (
            isinstance(incoming, str)
            and isinstance(published, str)
            and incoming != published
        ),
        "incomingVerifiedRawModelDraft": False,
        "factualQualityMeasured": False,
        "publicationGuardPassed": None,
        "containsAnswerText": False,
    }


__all__ = ["observe_publication_boundary"]
