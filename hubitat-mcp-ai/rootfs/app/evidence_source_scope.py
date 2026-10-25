"""Read-only source target fidelity across multi-round AI investigations.

The LLM may propose an app whose source is interesting but not linked to the
installed controller already verified in this request. Never treat that app's
source as the subject's implementation without a target-matched receipt.
This protects arbitrary devices and integrations, not named light fixtures.
"""
from __future__ import annotations

import re
from typing import Any


_IDENT = re.compile(r"^[1-9]\d{2,8}$")
_EXPLICIT_APP = re.compile(
    r"\b(?:app|application|rule)\s*(?:id\s*)?[:#]?\s*([1-9]\d{2,8})\b",
    re.I,
)


def _arg_app_id(receipt: dict[str, Any]) -> str:
    arguments = receipt.get("arguments")
    if not isinstance(arguments, dict):
        return ""
    nested = arguments.get("args")
    if isinstance(nested, dict):
        arguments = nested
    value = arguments.get("appId") or arguments.get("app_id")
    return str(value or "")


def verified_investigation_app_ids(
    receipts: list[dict[str, Any]],
) -> frozenset[str]:
    """Only host-validated, successful app-scoped reads anchor implementation."""
    matched: set[str] = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") not in (None, "read"):
            continue
        if row.get("evidence_kind") not in {
            "typed_existing_rule_partial_settings", "native_rule_evidence",
        }:
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        app_id = str(details.get("appId") or "")
        if not _IDENT.fullmatch(app_id) or app_id != _arg_app_id(row):
            continue
        matched.add(app_id)
    return frozenset(matched)


def source_app_scope_error(
    tool_name: str, arguments: dict[str, Any],
    receipts: list[dict[str, Any]], request: str,
) -> str | None:
    """Refuse unrelated source workbench targets after verified target reads.

    No inferred IDs and no generic string search through sensitive MCP results.
    A user explicitly naming multiple apps may compare them, but other app IDs
    require target-linked read evidence first. This never blocks an ordinary
    read of app configuration to discover that relationship.
    """
    if tool_name != "homebrain_read_groovy_source":
        return None
    selected = str(arguments.get("appId") or "")
    if not _IDENT.fullmatch(selected):
        return None  # The tool schema enforces validity.
    verified = verified_investigation_app_ids(receipts)
    if not verified:
        return None  # No established app target yet.
    explicitly_named = frozenset(_EXPLICIT_APP.findall(str(request or "")))
    if selected in verified or selected in explicitly_named:
        return None
    return (
        f"Source target mismatch: app {selected} is not among the "
        f"verified investigated app instance IDs ({', '.join(sorted(verified))}). "
        "Read target-linked app metadata or its exact installed source first; "
        "do not substitute a parent, similarly named, or neighboring app "
        "without proving the relationship. No source call was executed."
    )


__all__ = ["verified_investigation_app_ids", "source_app_scope_error"]
