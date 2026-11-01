"""Stage 6.10: strict source-container vs leaf record citation boundary.

No citation repair, guessed mapping, second request, or causal certification.
Classifies citation failures using static, safe error text only. Caller-supplied
allowlists contain only the fictional records already inspected by the model.
"""
from __future__ import annotations

from typing import Any


def validate_leaf_citations(
    kind: Any, ids: Any, *, allowed_kinds: frozenset[str],
    allowed_record_ids: set[str], source_container_ids: set[str],
) -> None:
    """Fail closed on unknown/ambiguous citations, never rewrite model IDs."""
    if type(kind) is not str or kind not in allowed_kinds:
        raise ValueError("invalid typed sentence citation kind")
    if type(ids) is not list or not 1 <= len(ids) <= 3 or any(
        type(item) is not str or not item or len(item) > 64 for item in ids
    ):
        raise ValueError("malformed evidence citation identifiers")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate evidence citation")
    if any(item in source_container_ids and item not in allowed_record_ids
           for item in ids):
        raise ValueError("source container used as evidence citation")
    if any(item not in allowed_record_ids for item in ids):
        raise ValueError("unknown evidence record citation")


__all__ = ["validate_leaf_citations"]
