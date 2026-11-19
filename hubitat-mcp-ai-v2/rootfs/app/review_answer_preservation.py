"""Conservative answer-preservation check after an optional model source review.

This does not score correctness or accept arbitrary drafts. When the later
model reply drops independently matched source timestamp anchors WITHOUT
obtaining any new successful read, preserve an earlier directly useful draft.
The existing causal/history publication gates still run on the chosen text.
"""
from __future__ import annotations

from receipt_grounding_anchors import receipt_grounding_anchors
from historical_publication import historical_publication_check


def preserve_receipt_anchored_answer(
    draft: str, revised: str, receipts: list[dict], *,
    receipt_count_at_draft: int | None,
    timezone_name: str = "Europe/London",
) -> tuple[str, str]:
    """Return published candidate and an explicit private diagnostic status.

    Only ORIGINAL returned event timestamps are anchors. App labels, invented
    numbers, model commentary and timestamps merely typed into prose aren't
    source evidence. Revisions with new successful reads cannot be rejected.
    """
    if not isinstance(draft, str) or not isinstance(revised, str):
        return revised, "not_applicable"
    if not draft.strip() or not revised.strip():
        return revised, "not_applicable_empty"
    if (type(receipt_count_at_draft) is not int
            or receipt_count_at_draft < 0
            or receipt_count_at_draft > len(receipts)):
        return revised, "not_applicable_missing_draft_boundary"
    if any(
        isinstance(row, dict) and row.get("success") is True
        and row.get("operation_executed") is not False
        for row in receipts[receipt_count_at_draft:]
    ):
        return revised, "new_successful_source_returned"
    anchors = set()
    for scope in receipt_grounding_anchors(
        receipts[:receipt_count_at_draft], timezone_name,
    ):
        for event in scope.get("events", []):
            stamp = event.get("source_timestamp")
            if isinstance(stamp, str):
                anchors.add(stamp)
    originals = {stamp for stamp in anchors if stamp in draft}
    # Reject a revision only on material loss of multiple independently
    # supported dated observations. This is a *completeness* lower bound,
    # never a claim that the original prose is fully factually correct.
    if len(originals) < 2:
        return revised, "insufficient_source_anchors"
    retained = sum(stamp in revised for stamp in originals)
    if retained:
        return revised, "source_anchors_partly_retained"
    # Do not preserve a draft already known to breach the historical
    # publication contract. A partial source-only fallback is safer.
    unsafe_reason, _ = historical_publication_check(
        draft, receipts[:receipt_count_at_draft],
    )
    if unsafe_reason is not None:
        return revised, "earlier_draft_historical_claim_unsafe"
    return draft, "source_anchored_draft_preserved_no_new_read"
