"""Source read utility and incident-window log overlap for native V2.

Host never selects tool calls. Return only evidence about observed source
integrity and repeat-query usefulness; no raw Groovy, settings or secrets
are passed to the model. Parsed names are not execution or causal proof.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _unwrap(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    # Match the existing source-reader's supported nested envelopes.
    for key in ("result", "data", "output"):
        inner=data.get(key)
        if isinstance(inner, dict):
            return inner
    return data


def source_read_summary(
    data: Any, *,
    requested_type: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    raw=_unwrap(data)
    out: dict[str, Any] = {
        "source_content_projected": False,
        "source_complete": False,
        "source_read_usable_for_method_reasoning": False,
    }
    if type(raw.get("success")) is bool:
        out["gateway_success"] = raw["success"]
    if isinstance(raw.get("status"), str):
        # Whitelist status rather than reflecting arbitrary untrusted strings.
        status=raw["status"].casefold()
        out["gateway_status"] = status if status in (
            "success", "ok", "error", "failed", "not_found") else "unclassified"
    if requested_type in ("app", "driver"):
        out["requested_source_type"] = requested_type
    if requested_id is not None and str(requested_id).isdecimal():
        out["requested_source_id"] = str(requested_id)
    source_id = raw.get("driverId") or raw.get("appId") or raw.get("id")
    if source_id is not None and str(source_id).isdecimal():
        out["returned_source_id"] = str(source_id)
    if (out.get("requested_source_id") and out.get("returned_source_id")):
        out["source_id_matches_request"] = (
            out["requested_source_id"] == out["returned_source_id"])
    # Code may be in supported nested response containers. Never return raw
    # strings or fragments merely because the tool itself returned success.
    from groovy_source_investigation import _source_body, _utf16_units
    body, meta=_source_body(data)
    # A short or single-line raw source is still *present*, even when it
    # cannot meet the completeness requirements for Groovy method analysis.
    # Preserve the prior privacy contract without exposing any text.
    source_keys = ("source", "sourceCode", "rawSource", "sourceText",
                   "sourceChunk", "chunk", "content", "code", "text")
    containers=[raw]
    for wrapper in ("result", "data", "output"):
        child=raw.get(wrapper)
        if isinstance(child, dict):
            containers.append(child)
    content_present = bool(body) or any(
        isinstance(item.get(key), str) and bool(item[key])
        for item in containers for key in source_keys
    )
    out["source_content_available"] = content_present
    if not body:
        out["source_read_status"] = (
            "source_text_present_but_not_extractable"
            if content_present else "no_source_text_in_returned_payload")
        out["source_inspection_blocker"] = (
            "Source is absent or not a complete extractable Groovy body. "
            "No implementation method was inspected; check source ID/type, "
            "source coverage and endpoint/permissions. Do not infer "
            "method absence or causation.")
        return out
    total=meta.get("totalLength")
    offset=meta.get("offset",0)
    declared=meta.get("driverId") or meta.get("appId") or meta.get("id")
    mismatch=(
        out.get("requested_source_id") and declared is not None
        and str(declared) != out["requested_source_id"]
    )
    complete=(
        not mismatch and meta.get("success") is not False
        and offset == 0 and type(total) is int
        and 0 < total <= 250000 and total in (len(body), _utf16_units(body))
        and "\ufffd" not in body
        and not any(0xD800 <= ord(c) <= 0xDFFF for c in body)
    )
    out["source_declared_total_units"] = total if type(total) is int else None
    out["source_offset"] = offset if type(offset) is int else None
    if not complete:
        out["source_read_status"] = "source_fragment_or_identity_unverified"
        out["source_inspection_blocker"] = (
            "Source was returned but complete contiguous coverage, source "
            "identity, or safe encoding was not verified. No method claims.")
        return out
    out["source_complete"] = True
    out["source_read_usable_for_method_reasoning"] = True
    out["source_read_status"] = "verified_contiguous_source"
    # Strictly lexical structural evidence; do not echo executable source.
    from groovy_method_scope import _definitions, _mask_non_code
    try:
        declarations=_definitions(body, _mask_non_code(body))
        names=[]
        for method in declarations:
            name=getattr(method,"name","")
            if (isinstance(name,str) and 0 < len(name) <= 80
                    and name.replace("_","a").isalnum()
                    and name not in names):
                names.append(name)
        out["declared_method_names"] = names[:40]
        out["declared_method_count_sample"] = len(names)
    except (ValueError, TypeError, AttributeError):
        out["method_declarations_unavailable"] = True
    out["source_interpretation_limit"] = (
        "Source declarations are code structure only; they do not prove "
        "runtime execution, scheduling or cause.")
    return out


def repeated_broad_log_scope(
    requested: Mapping[str, Any],
    witnesses: Sequence[Mapping[str, Any]],
) -> bool:
    """Detect same broad WARN query repeated with only a larger limit.

    Only reject when earlier requested limit exceeds actual returned rows.
    Changing any time bound, scope, severity, pattern or cursor is a distinct
    read. The source sample remains incomplete even when this holds.
    """
    if not isinstance(requested, Mapping):
        return False
    comparison=("mode","level","deviceId","appId","pattern","patterns",
                "since","until","cursor","sortBy")
    if any(requested.get(k) not in (None,"") for k in (
            "since","until","cursor","pattern","patterns")):
        return False
    mode=requested.get("mode","past")
    if mode!="past":
        return False
    limit=requested.get("limit")
    if type(limit) is not int or limit<1:
        return False
    for witness in witnesses:
        if witness.get("operation") != "hub_get_logs":
            continue
        old=witness.get("read_filters")
        source=witness.get("source_data")
        if not isinstance(old,Mapping) or not isinstance(source,Mapping):
            continue
        old_limit=old.get("limit")
        if type(old_limit) is not int or old_limit<1 or limit<=old_limit:
            continue
        if any(old.get(k, "past" if k=="mode" else None)
               != requested.get(k, "past" if k=="mode" else None)
               for k in comparison):
            continue
        rows=source.get("log_summary",{}).get("returned_rows")
        if type(rows) is int and 0 <= rows < old_limit:
            return True
    return False


__all__ = ["source_read_summary", "repeated_broad_log_scope"]
