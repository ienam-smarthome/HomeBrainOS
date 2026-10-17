"""Privacy-safe metadata for real MCP Groovy source reads.

Raw Groovy never enters evidence receipts. A successful tool response with only
a file pointer, status or zero-length source does not prove code was retrieved.
"""
from __future__ import annotations

from typing import Any

_SOURCE_OPS = frozenset({"hub_get_source", "homebrain_read_groovy_source"})
_MAX_SOURCE_TEXT = 1_000_000


def _data_records(value: Any) -> list[dict[str, Any]]:
    results = [value] if isinstance(value, dict) else []
    for item in list(results):
        for key in ("result", "data", "output"):
            nested = item.get(key)
            if isinstance(nested, dict):
                results.append(nested)
    return results[:8]


def source_read_metadata(
    gateway: str, arguments: dict[str, Any], data: Any,
) -> dict[str, Any] | None:
    """Return only bounded numeric/boolean source facts; never raw source."""
    operation = str(arguments.get("tool") or gateway)
    if operation not in _SOURCE_OPS:
        return None
    if operation == "homebrain_read_groovy_source":
        if not isinstance(data, dict):
            return {"sourceRetrieved": False, "fullImplementationVerified": False}
        result = {
            "sourceRetrieved": data.get("sourceRetrieved") is True,
            "fullImplementationVerified": data.get("fullImplementationVerified") is True,
        }
        for result_key, data_key in (
            ("verifiedCharacters", "verifiedCharacters"),
            ("declaredTotalCharacters", "declaredTotalCharacters"),
            ("verifiedPages", "verifiedPages"),
        ):
            value = data.get(data_key)
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= _MAX_SOURCE_TEXT:
                result[result_key] = value
        code_id = data.get("sourceCodeId")
        if isinstance(code_id, (int, str)) and str(code_id).isdigit():
            result["sourceCodeId"] = str(code_id)
        return result

    leaf = arguments.get("args")
    if not isinstance(leaf, dict):
        leaf = arguments
    for item in _data_records(data):
        for field in ("source", "sourceCode", "sourceChunk", "sourceText"):
            text = item.get(field)
            if not isinstance(text, str) or not (20 <= len(text) <= _MAX_SOURCE_TEXT):
                continue
            if item.get("success") is False:
                continue
            received_offset = item.get("offset", leaf.get("offset", 0))
            if not isinstance(received_offset, int) or received_offset < 0:
                continue
            # If the API reports Java UTF-16 offsets, use the verified
            # number of code units rather than Python's Unicode code points.
            # An unexplained nextOffset mismatch may be a missing character;
            # do not record a certifiable span for such a response.
            scalar_length = len(text)
            utf16_length = len(text.encode("utf-16-le", errors="surrogatepass")) // 2
            next_offset = item.get("nextOffset")
            span_length = scalar_length
            if isinstance(next_offset, int) and next_offset > received_offset:
                advertised_length = next_offset - received_offset
                if advertised_length in (scalar_length, utf16_length):
                    span_length = advertised_length
                else:
                    span_length = None
            result: dict[str, Any] = {
                "sourceRetrieved": True,
                "offset": received_offset,
            }
            if span_length is not None:
                result["chunkLength"] = span_length
            total = item.get("totalLength")
            if isinstance(total, int) and 0 < total <= _MAX_SOURCE_TEXT:
                result["totalLength"] = total
            code_id = item.get("appId") or leaf.get("id")
            if isinstance(code_id, (int, str)) and str(code_id).isdigit():
                result["sourceCodeId"] = str(code_id)
            return result
    return {"sourceRetrieved": False}


def contiguous_source_coverage(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prove a complete byte/character offset span from actual source receipts."""
    spans: list[tuple[int, int]] = []
    totals: set[int] = set()
    ids: set[str] = set()
    for receipt in receipts:
        if (not isinstance(receipt, dict) or
                receipt.get("success") is not True or
                receipt.get("mutates") is True):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict) or details.get("sourceRetrieved") is not True:
            continue
        total = details.get("totalLength")
        offset = details.get("offset")
        count = details.get("chunkLength")
        if isinstance(total, int) and total > 0:
            totals.add(total)
        source_id = details.get("sourceCodeId")
        if source_id is not None:
            ids.add(str(source_id))
        if (isinstance(offset, int) and offset >= 0
                and isinstance(count, int) and count > 0):
            spans.append((offset, offset + count))
    if len(totals) != 1 or len(ids) > 1:
        return {"fullImplementationVerified": False,
                "chunksObserved": len(spans), "coverage": "unverified"}
    total = next(iter(totals))
    end = 0
    for start, stop in sorted(spans):
        if start > end:
            return {"fullImplementationVerified": False,
                    "chunksObserved": len(spans), "coverage": "gapped"}
        end = max(end, stop)
    return {"fullImplementationVerified": bool(spans) and end >= total,
            "chunksObserved": len(spans),
            "coverage": "complete" if spans and end >= total else "partial",
            "totalLength": total}


__all__ = ["source_read_metadata", "contiguous_source_coverage"]
