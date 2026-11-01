"""Domain-independent admission of a model-selected, SOURCE-RENDERED claim plan.

A domain adapter must first construct its fact catalog from independently
validated, scope-matched source receipts. This module checks a plan's shape,
selection and mandatory uncertainty; it does NOT establish that arbitrary
sentences are true or certify free-form language. Only host-supplied catalog
sentences may reach publication. No model/MCP calls or device actions occur.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

SCHEMA = "homebrain-source-claim-plan.v1"
_CLAIM_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def admit_source_claim_plan(
    draft: Any,
    facts: Mapping[str, str] | None,
    mandatory_ids: Iterable[str],
) -> tuple[str | None, str]:
    """Fail closed unless the source adapter's mandatory facts are selected.

    The caller, never the model, supplies the source-attested fact catalog and
    its required caveats. A matching schema is a *selection* certificate, not
    semantic entailment or evidence of physical execution.
    """
    if not isinstance(facts, Mapping) or not facts:
        return None, "no-source-claims"
    if not isinstance(draft, str) or len(draft) > 1500:
        return None, "not-a-bounded-plan"
    try:
        item = json.loads(draft.strip())
    except (TypeError, ValueError):
        return None, "not-a-json-plan"
    if not isinstance(item, dict) or set(item) != {"schema", "claim_ids"}:
        return None, "unexpected-plan-fields"
    if item["schema"] != SCHEMA:
        return None, "unknown-plan-schema"
    ids = item["claim_ids"]
    if (
        not isinstance(ids, list) or not 3 <= len(ids) <= 7
        or any(not isinstance(value, str) or not _CLAIM_ID.fullmatch(value)
               for value in ids)
        or len(set(ids)) != len(ids)
    ):
        return None, "malformed-claims"
    if any(value not in facts for value in ids):
        return None, "unsupported-claim"
    mandatory = frozenset(mandatory_ids)
    if (
        not mandatory or not mandatory.issubset(ids)
        or not mandatory.issubset(facts)
        or any(not isinstance(value, str) or not _CLAIM_ID.fullmatch(value)
               for value in mandatory)
    ):
        return None, "missing-material-proof"
    # Never emit a model-authored claim or an arbitrary object repr. This
    # validation is defence-in-depth; callers must ALSO source-verify facts.
    if any(
        not isinstance(facts[key], str) or not facts[key].strip()
        or len(facts[key]) > 1000
        or any(ord(char) < 32 and char not in "\t\n" for char in facts[key])
        for key in ids
    ):
        return None, "invalid-source-fact"
    return "\n\n".join(facts[key] for key in ids), "source-claim-plan-admitted"


__all__ = ["SCHEMA", "admit_source_claim_plan"]
