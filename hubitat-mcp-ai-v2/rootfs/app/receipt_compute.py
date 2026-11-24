"""Deterministic, read-only computation over rows already returned this request.

Models are unreliable at counting, filtering, averaging and timestamp
arithmetic over long native results (5 vs 6 devices, 36 KB vs 36,074.5 KB).
This helper lets the MODEL choose a prior successful receipt and a structured
operation; the client only computes. It never reads the hub, parses the user's
prompt, selects a device/tool, retries, or grants any permission.

Every result states which receipt/rows were used, how many rows were skipped
and why, and whether the receipt was truncated, so a computed number cannot be
mistaken for coverage the source never had.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

TOOL_NAME = "homebrain_compute_receipt"
MAX_ROWS = 50000
MAX_OUTPUT_ROWS = 200
_OPS = ("count", "unique_count", "min", "max", "mean", "sum", "sort",
        "group_count", "time_gaps", "diff")
_COMPARATORS = ("eq", "ne", "lt", "lte", "gt", "gte", "contains", "exists", "missing")

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Deterministically count/filter/aggregate rows ALREADY RETURNED by an "
            "earlier successful tool call in THIS request. Use it instead of "
            "counting, averaging, sorting or subtracting timestamps yourself. "
            "receipt_index (optional) is the 1-based position of an earlier call in "
            "this request; omit it to use the most recent successful native data "
            "read. For a paginated result pass receipt_indexes=[page receipts] to "
            "combine them. If it is wrong the error lists the usable receipts. rows_path is a dotted path to the list "
            "(e.g. 'devices' or 'content.0.text.entries'); omit it to use the "
            "largest list of objects. Optional where=[{field,op,value}] filters rows "
            "first (op: eq, ne, lt, lte, gt, gte, contains, exists, missing; "
            "dotted field names allowed). operation: count, unique_count(field), "
            "min/max/mean/sum(field), sort(field, descending, limit), "
            "group_count(field), time_gaps(field = timestamp field; returns the "
            "largest gaps between adjacent rows), diff(field; newest minus "
            "oldest ISO timestamp, or last minus first numeric in returned order). "
            "Timestamps must be ISO strings with a UTC offset or Z; naive or epoch "
            "values are not guessed. Output reports rows used and skipped. "
            "It reads no hub data and proves nothing about rows the source did not return."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "receipt_index": {"type": "integer", "minimum": 1},
                "receipt_indexes": {
                    "type": "array", "minItems": 2, "maxItems": 12,
                    "items": {"type": "integer", "minimum": 1},
                    "description": ("Pages of ONE paginated result: rows from these "
                                    "receipts are combined (rows with the same id "
                                    "are counted once and reported)."),
                },
                "rows_path": {"type": "string", "maxLength": 200},
                "where": {
                    "type": "array", "maxItems": 8,
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "maxLength": 100},
                            "op": {"type": "string", "enum": list(_COMPARATORS)},
                            "value": {},
                        },
                        "required": ["field", "op"],
                        "additionalProperties": False,
                    },
                },
                "operation": {"type": "string", "enum": list(_OPS)},
                "field": {"type": "string", "maxLength": 100},
                "descending": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_OUTPUT_ROWS},
            },
            "required": ["operation"],
            "additionalProperties": False,
        },
    },
}


class ComputeError(ValueError):
    """Invalid structured arguments or an unusable receipt."""


def _decode(value: Any) -> Any:
    """Decode MCP text parts that themselves contain JSON."""
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "[{":
            try:
                return json.loads(text)
            except ValueError:
                return value
    return value


def _walk(value: Any, path: list[str]) -> Any:
    current = _decode(value)
    for key in path:
        current = _decode(current)
        if isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                raise ComputeError(f"rows_path segment {key!r} is not a valid list index") from None
        elif isinstance(current, dict):
            if key not in current:
                raise ComputeError(f"rows_path segment {key!r} not found in receipt")
            current = current[key]
        else:
            raise ComputeError(f"rows_path segment {key!r} cannot descend into a scalar")
    return _decode(current)


def _find_rows(value: Any, depth: int = 0) -> tuple[str, list] | None:
    """Largest list of objects, searched breadth-first to a small depth."""
    best: tuple[str, list] | None = None
    queue: list[tuple[str, Any, int]] = [("", _decode(value), 0)]
    while queue:
        prefix, node, level = queue.pop(0)
        node = _decode(node)
        if isinstance(node, list):
            if node and all(isinstance(x, dict) for x in node):
                if best is None or len(node) > len(best[1]):
                    best = (prefix, node)
            if level < 4:
                for i, child in enumerate(node[:3]):
                    queue.append((f"{prefix}.{i}" if prefix else str(i), child, level + 1))
        elif isinstance(node, dict) and level < 4:
            for key, child in node.items():
                queue.append((f"{prefix}.{key}" if prefix else key, child, level + 1))
    return best


def _field(row: dict, name: str) -> Any:
    current: Any = row
    for part in name.split("."):
        current = _decode(current)
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover
        return "<missing>"


_MISSING = _Missing()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _instant(value: Any) -> datetime | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None  # a naive time has no defined instant
        return parsed.astimezone(UTC)
    return None


def _matches(row: dict, clause: dict) -> bool:
    field, op = clause.get("field"), clause.get("op")
    if not isinstance(field, str) or op not in _COMPARATORS:
        raise ComputeError("Each where clause needs a field and a supported op")
    actual = _field(row, field)
    if op == "exists":
        return actual is not _MISSING and actual is not None
    if op == "missing":
        return actual is _MISSING or actual is None
    if actual is _MISSING or actual is None:
        return False
    expected = clause.get("value")
    if op in ("eq", "ne"):
        a, e = _number(actual), _number(expected)
        same = (a == e) if a is not None and e is not None else str(actual) == str(expected)
        return same if op == "eq" else not same
    if op == "contains":
        return str(expected).lower() in str(actual).lower()
    a, e = _number(actual), _number(expected)
    if a is None or e is None:
        ia, ie = _instant(actual), _instant(expected)
        if ia is None or ie is None:
            return False
        a, e = ia.timestamp(), ie.timestamp()
    return {"lt": a < e, "lte": a <= e, "gt": a > e, "gte": a >= e}[op]


def _clean(value: float) -> float | int:
    return int(value) if float(value).is_integer() and abs(value) < 1e15 else round(value, 6)


def _fmt_seconds(seconds: float) -> str:
    whole, frac = divmod(abs(seconds), 1)
    hours, rem = divmod(int(whole), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{'-' if seconds < 0 else ''}{hours}h {minutes}m {secs + frac:.3f}s"


def _receipt_rows(receipt: dict, rows_path: str | None) -> tuple[str, list]:
    raw = receipt.get("response")
    if not isinstance(raw, str):
        raise ComputeError("That receipt has no stored response")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise ComputeError("That receipt response is not JSON") from None
    if isinstance(payload, dict) and payload.get("truncated") is True:
        raise ComputeError(
            "That receipt was truncated by the context limit; computing on it would "
            "silently omit rows. Re-query with a narrower scope.")
    root = payload.get("mcp_result", payload) if isinstance(payload, dict) else payload
    if rows_path:
        found = _walk(root, [p for p in rows_path.split(".") if p != ""])
        path = rows_path
    else:
        located = _find_rows(root)
        if located is None:
            raise ComputeError("No list of objects found; supply rows_path")
        path, found = located
    if not isinstance(found, list):
        raise ComputeError("rows_path does not point to a list")
    return path, found


def compute(receipts: list[dict], args: dict) -> dict:  # noqa: C901
    """Compute from structured model arguments over this request's receipts."""
    allowed = {"receipt_index", "receipt_indexes", "rows_path", "where", "operation", "field",
               "descending", "limit"}
    if not isinstance(args, dict) or set(args) - allowed:
        raise ComputeError("Unexpected arguments for receipt computation")
    operation = args.get("operation")
    if operation not in _OPS:
        raise ComputeError(f"operation must be one of {', '.join(_OPS)}")
    eligible = [i for i, r in enumerate(receipts, 1)
                if r.get("success") is True and r.get("result_kind") == "tool_result"]
    catalog = [{"receipt_index": i, "tool": receipts[i - 1].get("name"),
                "arguments": receipts[i - 1].get("arguments")} for i in eligible[-12:]]
    multi = args.get("receipt_indexes")
    if multi is not None and "receipt_index" in args:
        raise ComputeError("Use receipt_index or receipt_indexes, not both")
    if multi is not None:
        if (not isinstance(multi, list) or not 2 <= len(multi) <= 12
                or any(type(i) is not int for i in multi) or len(set(multi)) != len(multi)):
            raise ComputeError("receipt_indexes must be 2-12 distinct integers")
        indexes = list(multi)
    else:
        index = args.get("receipt_index")
        if index is None:
            if not eligible:
                raise ComputeError("No successful native data read exists in this request yet")
            index = eligible[-1]
        indexes = [index]
    for index in indexes:
        if type(index) is not int or index not in eligible:
            raise ComputeError(
                "receipt_index is not a successful native data read in this request; "
                f"usable receipts: {json.dumps(catalog, default=str)[:1500]}")
    path_text = args.get("rows_path")
    if path_text is not None and not isinstance(path_text, str):
        raise ComputeError("rows_path must be text")
    found: list = []
    per_receipt: list[dict] = []
    rows_path = path_text or ""
    for index in indexes:
        path_used, page_rows = _receipt_rows(receipts[index - 1], path_text)
        rows_path = rows_path or path_used
        per_receipt.append({"receipt_index": index, "rows": len(page_rows),
                            "tool": receipts[index - 1].get("name")})
        found.extend(page_rows)
    receipt = receipts[indexes[0] - 1]
    index = indexes[0]
    duplicates_removed = 0
    if len(indexes) > 1:
        seen_ids: set[str] = set()
        unique_rows = []
        for row in found:
            row_id = row.get("id") if isinstance(row, dict) else None
            if row_id is not None:
                key = json.dumps(row_id, sort_keys=True, default=str)
                if key in seen_ids:
                    duplicates_removed += 1
                    continue
                seen_ids.add(key)
            unique_rows.append(row)
        found = unique_rows
    if len(found) > MAX_ROWS:
        raise ComputeError(f"List has {len(found)} rows (limit {MAX_ROWS})")
    rows = [r for r in found if isinstance(r, dict)]
    non_object = len(found) - len(rows)
    where = args.get("where") or []
    if not isinstance(where, list) or len(where) > 8:
        raise ComputeError("where must be a list of at most 8 clauses")
    selected = [r for r in rows if all(_matches(r, c) for c in where)]
    out: dict[str, Any] = {
        "source": "client computation over an earlier successful receipt in this request",
        "receipt_index": index if len(indexes) == 1 else indexes,
        "receipt_tool": receipt.get("name"),
        "receipts_combined": per_receipt if len(indexes) > 1 else None,
        "duplicate_id_rows_removed": duplicates_removed if len(indexes) > 1 else None,
        "rows_path": rows_path,
        "rows_in_list": len(found),
        "rows_non_object_ignored": non_object,
        "rows_after_filter": len(selected),
        "filters_applied": where,
        "operation": operation,
        "covers_only_rows_the_source_returned": True,
        "note": ("Computed from returned rows only. Unreturned, paginated, row-limited "
                 "or unqueried data is unknown; this does not establish source completeness."),
    }
    field = args.get("field")
    if operation == "count":
        out["count"] = len(selected)
        return out
    if not isinstance(field, str) or not field:
        raise ComputeError(f"operation {operation!r} needs a field")
    out["field"] = field
    values = [(r, _field(r, field)) for r in selected]
    present = [(r, v) for r, v in values if v is not _MISSING and v is not None]
    out["rows_missing_field"] = len(values) - len(present)
    if operation == "unique_count":
        out["unique_count"] = len({json.dumps(v, sort_keys=True, default=str) for _, v in present})
        return out
    if operation == "group_count":
        groups: dict[str, int] = {}
        for _, v in present:
            key = v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
            groups[key] = groups.get(key, 0) + 1
        ordered = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
        out["groups"] = [{"value": k, "count": c} for k, c in ordered[:MAX_OUTPUT_ROWS]]
        out["group_count"] = len(groups)
        return out
    limit = args.get("limit", 20)
    if type(limit) is not int or not 1 <= limit <= MAX_OUTPUT_ROWS:
        raise ComputeError(f"limit must be 1..{MAX_OUTPUT_ROWS}")
    if operation in ("min", "max", "mean", "sum"):
        nums = [(r, _number(v)) for r, v in present]
        usable = [(r, n) for r, n in nums if n is not None]
        out["rows_non_numeric"] = len(present) - len(usable)
        out["rows_used"] = len(usable)
        if not usable:
            out["result"] = None
            out["note_empty"] = "No numeric values; no result computed."
            return out
        values_only = [n for _, n in usable]
        if operation == "min":
            out["result"] = _clean(min(values_only))
        elif operation == "max":
            out["result"] = _clean(max(values_only))
        elif operation == "sum":
            out["result"] = _clean(math.fsum(values_only))
        else:
            out["result"] = _clean(math.fsum(values_only) / len(values_only))
            out["min"] = _clean(min(values_only))
            out["max"] = _clean(max(values_only))
        return out
    if operation == "sort":
        keyed = []
        for r, v in present:
            n = _number(v)
            keyed.append((r, n if n is not None else (_instant(v).timestamp() if _instant(v) else None), v))
        usable = [k for k in keyed if k[1] is not None]
        out["rows_not_sortable"] = len(keyed) - len(usable)
        usable.sort(key=lambda k: k[1], reverse=bool(args.get("descending")))
        out["rows"] = [r for r, _, _ in usable[:limit]]
        out["rows_returned"] = len(out["rows"])
        out["rows_truncated_to_limit"] = len(usable) > limit
        return out
    # time_gaps / diff need instants or numbers
    stamps = []
    for r, v in present:
        moment = _instant(v)
        if moment is not None:
            stamps.append((moment, r, v))
    if operation == "time_gaps":
        out["rows_unparseable_time"] = len(present) - len(stamps)
        stamps.sort(key=lambda s: s[0])
        gaps = []
        for (a, _, av), (b, _, bv) in zip(stamps, stamps[1:]):
            seconds = (b - a).total_seconds()
            gaps.append({"from": av, "to": bv, "seconds": round(seconds, 3),
                         "readable": _fmt_seconds(seconds)})
        if len(gaps) <= 50:
            out["gaps_in_time_order"] = list(gaps)
        gaps.sort(key=lambda g: -g["seconds"])
        out["rows_used"] = len(stamps)
        out["adjacent_gaps"] = len(gaps)
        out["largest_gaps"] = gaps[:limit]
        out["gaps_are_between_returned_rows_not_proof_of_no_events"] = True
        return out
    # diff: newest minus oldest. Timestamps give seconds; numbers give delta.
    if stamps and len(stamps) == len(present) and len(stamps) >= 2:
        stamps.sort(key=lambda s: s[0])
        seconds = (stamps[-1][0] - stamps[0][0]).total_seconds()
        out.update({"kind": "timestamp_span", "oldest": stamps[0][2], "newest": stamps[-1][2],
                    "seconds": round(seconds, 3), "readable": _fmt_seconds(seconds),
                    "rows_used": len(stamps)})
        return out
    nums = [(r, _number(v)) for r, v in present]
    usable = [n for _, n in nums if n is not None]
    if len(usable) < 2:
        raise ComputeError("diff needs at least two numeric or timestamp values")
    out.update({"kind": "numeric_last_minus_first_in_returned_order",
                "first": _clean(usable[0]), "last": _clean(usable[-1]),
                "difference": _clean(usable[-1] - usable[0]), "rows_used": len(usable),
                "rows_non_numeric": len(present) - len(usable)})
    return out


HINT_MIN_ROWS = 10
_HINT_MAX_FIELDS = 40


def _field_names(rows: list) -> list[str]:
    """Top-level and one-level-nested field names seen in the first rows."""
    seen: dict[str, None] = {}
    for row in rows[:200]:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            seen.setdefault(key, None)
            value = _decode(value)
            if isinstance(value, dict):
                for inner in list(value)[:20]:
                    seen.setdefault(f"{key}.{inner}", None)
    return list(seen)[:_HINT_MAX_FIELDS]


def rows_hint(result: Any, receipt_index: int) -> dict | None:
    """Structural pointer for a native result holding many rows.

    Based only on the SHAPE of the returned source (a list of objects), never on
    the user's wording, so it stays within the no-prompt-keyword rule. It names
    the receipt, list path and real field names so the model can compute counts,
    ranges, averages, rankings and gaps exactly instead of by inspection.
    """
    located = _find_rows(result)
    if located is None:
        return None
    path, rows = located
    if len(rows) < HINT_MIN_ROWS or len(rows) > MAX_ROWS:
        return None
    return {
        "source": "client observation of this result's shape; not hub data",
        "receipt_index": receipt_index,
        "rows_path": path,
        "rows_returned": len(rows),
        "field_names_seen": _field_names(rows),
        "use": (f"For any count, range, average, ranking or timestamp gap over "
                f"these rows call {TOOL_NAME} with receipt_index={receipt_index} "
                "rather than calculating by inspection. If this is one page of several, "
                "pass receipt_indexes=[all page receipts]. Missing/unreturned rows "
                "stay unknown."),
    }
