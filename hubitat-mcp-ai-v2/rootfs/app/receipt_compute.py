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
import re
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
            "values are not guessed. The one exception: lt/lte/gt/gte on 'MM-DD HH:MM:SS' "
            "stamps (as hub history rows use) compare as text within one calendar year, so a "
            "time window can be a where range on that field. Output reports rows used and skipped. "
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
                nested = _decode(current.get("modes")) if isinstance(current.get("modes"), (dict, str)) else None
                if isinstance(nested, dict) and key in nested:
                    current = nested[key]  # tolerate content.0.text.apps.entries for modes.apps.entries
                    continue
                known = ", ".join(sorted(str(k) for k in current)[:12])
                raise ComputeError(f"rows_path segment {key!r} not found in receipt; keys here: {known}")
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
            if level < 7:
                for i, child in enumerate(node[:3]):
                    queue.append((f"{prefix}.{i}" if prefix else str(i), child, level + 1))
        elif isinstance(node, dict) and level < 7:
            for key, child in node.items():
                if isinstance(key, str) and key.startswith("client_"):
                    continue  # client-added annotations are not source rows
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


_MD_STAMP = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d$")


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
    if (a is None or e is None) and _MD_STAMP.match(str(actual)) and _MD_STAMP.match(str(expected)):
        sa, se = str(actual), str(expected)
        return {"lt": sa < se, "lte": sa <= se, "gt": sa > se, "gte": sa >= se}[op]
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


def compute(receipts: list[dict], args: dict) -> dict:
    """Compute, then add unit conversions for fields whose name ends in KB."""
    out = _compute(receipts, args)
    field = args.get("field") if isinstance(args, dict) else None
    local = out if isinstance(out, dict) else None
    if isinstance(local, dict) and isinstance(field, str) and field.lower() in ("statesize",) \
            or isinstance(field, str) and field.lower().endswith("bytes"):
        converted = {}
        for key in ("result", "min", "max"):
            value = local.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                converted[key] = {"KB_decimal": round(value / 1000, 6),
                                  "KiB_binary": round(value / 1024, 6)}
        if converted:
            local["unit_conversions_from_bytes"] = converted
    if isinstance(local, dict) and isinstance(field, str) and isinstance(local.get("rows"), list) \
            and (field.lower() == "statesize" or field.lower().endswith("bytes")):
        key = f"client_{field}_KB_decimal"
        local["rows"] = [dict(r, **{key: round(r[field] / 1000, 3)})
                         if isinstance(r, dict) and isinstance(r.get(field), (int, float))
                         and not isinstance(r.get(field), bool) else r
                         for r in local["rows"]]
    if isinstance(local, dict) and isinstance(field, str) and field.lower().endswith("kb"):
        converted = {}
        for key in ("result", "min", "max"):
            value = local.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                converted[key] = {"MB_decimal": round(value / 1000, 6),
                                  "MiB_binary": round(value / 1024, 6)}
        if converted:
            local["unit_conversions_from_KB"] = converted
    return out


def _compute(receipts: list[dict], args: dict) -> dict:  # noqa: C901
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
        "same_source_receipts_not_included": _same_source_pages(receipts, indexes, eligible),
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


def rows_hint(result: Any, receipt_index: int, args: dict | None = None) -> dict | None:
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
    hint = {
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
    coverage = _row_coverage(result, path, len(rows))
    if coverage is not None:
        ordered = _ordered_by_source(rows, args)
        if ordered is not None:
            coverage["ordered_by_source"] = ordered
            if coverage.get("partial"):
                coverage["use"] = (
                    f"The call asked the source to sort by `{ordered['field']}` "
                    f"({ordered['argument']} argument) and the rows came back "
                    f"{ordered['direction']} by that field, so these are the leading rows of "
                    "the source's own ordering, not an arbitrary subset. Say that they are the "
                    "source-ordered leading rows out of M, and that whether the source applied "
                    "the sort before paging was not independently verified. To read more, call "
                    "the same tool again with the next_cursor exactly as returned.")
        hint["coverage"] = coverage
    return hint


_SORT_ARGS = ("sortBy", "sort_by", "orderBy", "order_by")


def _ordered_by_source(rows: list, args: dict | None) -> dict | None:
    """The sort field the call named, when the returned rows really follow it."""
    if not isinstance(args, dict):
        return None
    for key in _SORT_ARGS:
        raw = args.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        field = raw.strip().split(":")[0].split()[0]
        values = []
        for row in rows:
            value = row.get(field) if isinstance(row, dict) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            values.append(value)
        if len(values) < 2:
            return None
        if all(a >= b for a, b in zip(values, values[1:])):
            return {"field": field, "argument": key, "direction": "descending"}
        if all(a <= b for a, b in zip(values, values[1:])):
            return {"field": field, "argument": key, "direction": "ascending"}
        return None
    return None


_PAGING_KEYS = {"cursor", "offset", "page", "pageToken"}


def _page_signature(receipt: dict) -> tuple:
    """Tool name plus arguments with paging keys removed (structural)."""
    args = receipt.get("arguments") if isinstance(receipt.get("arguments"), dict) else {}
    kept = {k: v for k, v in args.items() if k not in _PAGING_KEYS}
    return receipt.get("name"), json.dumps(kept, sort_keys=True, default=str)


def _same_source_pages(receipts: list[dict], indexes: list[int],
                       eligible: list[int]) -> list[int] | None:
    """Other receipts that are further pages of the same read, left out of this computation."""
    first = receipts[indexes[0] - 1]
    wanted = _page_signature(first)
    extra = [i for i in eligible if i not in indexes
             and _page_signature(receipts[i - 1]) == wanted]
    return extra or None


def issued_cursors(result: Any, depth: int = 0) -> set[str]:
    """Every nextCursor value a source result handed back (structural walk)."""
    found: set[str] = set()
    value = _decode(result)
    if depth > 6:
        return found
    if isinstance(value, dict):
        cursor = value.get("nextCursor")
        if cursor not in (None, "", False):
            found.add(str(cursor))
        for item in value.values():
            found |= issued_cursors(item, depth + 1)
    elif isinstance(value, list):
        for item in value[:50]:
            found |= issued_cursors(item, depth + 1)
    return found


def cursor_continuation(name: str, args: dict, receipts: list[dict]):
    """Arguments to send for a paging read, or a reason to refuse it.

    A cursor only continues the exact read that issued it: the hub rejected
    the same cursor when the page size, mode form or other arguments differed
    (for example a default page size of 20 against a cursor from an unlimited
    read, or a one-item mode list next to a cursor). Structural only, from
    receipts. Returns (args_to_send, refusal_text, note).
    """
    if not isinstance(args, dict) or "cursor" not in args:
        return args, None, None
    cursor = args["cursor"]
    if cursor in (None, ""):
        sent = {k: v for k, v in args.items() if k != "cursor"}
        return sent, None, "An empty cursor was removed; this is a first-page read."
    for number, item in enumerate(receipts, 1):
        if (isinstance(item, dict) and item.get("name") == name and item.get("success")
                and str(cursor) in (item.get("issued_cursors") or [])
                and isinstance(item.get("arguments"), dict)):
            canonical = {k: v for k, v in item["arguments"].items() if k != "cursor"}
            mode = canonical.get("mode")
            if isinstance(mode, list) and len(mode) == 1:
                canonical["mode"] = mode[0]
            canonical["cursor"] = cursor
            if canonical == args:
                return args, None, None
            changed = sorted(k for k in set(canonical) | set(args)
                             if canonical.get(k) != args.get(k))
            return canonical, None, (
                f"This cursor continues the read in receipt {number}, so it was sent with "
                f"that read's arguments (single-value mode, same page size). Arguments "
                f"changed from yours: {', '.join(changed)}.")
    return args, (f"cursor {cursor!r} was not returned by an earlier {name} read in this "
                  "request, so it was not sent to the hub. A cursor is only valid for the "
                  "read that issued it. Repeat the read without a cursor, then page with "
                  "the nextCursor it returns."), None


def _row_coverage(result: Any, path: str, returned: int) -> dict | None:
    """Report rows the source says exist but did not return (shape-based)."""
    try:
        parent = _walk(result, [p for p in path.split(".") if p != ""][:-1])
    except ComputeError:
        return None
    if not isinstance(parent, dict):
        return None
    reported = next((parent[k] for k in ("total", "matched", "totalCount")
                     if isinstance(parent.get(k), (int, float))
                     and not isinstance(parent.get(k), bool)), None)
    cursor = parent.get("nextCursor")
    if reported is None and not cursor:
        return None
    partial = (reported is not None and returned < reported) or bool(cursor)
    out: dict[str, Any] = {"rows_returned": returned, "source_reported_total": reported,
                           "partial": partial}
    if cursor:
        out["next_cursor"] = cursor
    if partial:
        out["use"] = ("This is only part of what the source holds. A ranking, count or "
                      "maximum over these rows covers only these rows: say so in the answer "
                      "(for example 'N of M rows'). To read more, call the same tool again "
                      "with the next_cursor exactly as returned, following the tool's own "
                      "paging rules; if that read fails, report the result as partial.")
    return out


# Field meanings for the hub's per-device runtime table, keyed on the declared
# tool name and the returned field names (never on the user's wording).
_RUNTIME_TABLE_FIELDS = ("pct", "pctTotal", "total", "grandTotal", "stateSize")


def field_meaning_note(tool_name: str, result: Any) -> dict | None:
    """Explain what the runtime-table fields of hub_get_logs rows measure."""
    if tool_name != "hub_get_logs":
        return None
    located = _find_rows(result)
    if located is None:
        return None
    path, rows = located
    names = set(_field_names(rows))
    present = [field for field in _RUNTIME_TABLE_FIELDS if field in names]
    if "pct" not in present or "total" not in present:
        return None
    return {
        "source": "client note on field names seen in this result; not hub data",
        "rows_path": path,
        "meanings": {
            "total": "runtime in milliseconds for the sampled window (not memory)",
            "grandTotal": "runtime in milliseconds summed over all rows in the table (not memory)",
            "pct": "this row's share of that total runtime (not a share of memory)",
            "pctTotal": "this row's share of the whole hub uptime (not memory)",
            "stateSize": "bytes of stored state for this device or app (the only size-like field here)",
            "average": "average runtime per call in milliseconds",
            "count": "number of runtime samples",
        },
        "use": ("None of these fields is RAM or memory use. Report them under their "
                "own names; do not title a column Memory or RAM. For KB use the "
                "client_*_KB_decimal value (bytes divided by 1,000), never bytes divided "
                "by 1,024. For hub-wide free memory use a memory source "
                "(hub_get_memory_history or hub_get_metrics); a per-device memory "
                "figure is not provided by this table."),
    }


def partial_coverage_note(receipts: list[dict]) -> str | None:
    """Deterministic footnote when a computation ran over a partial row result.

    Structural only: it reads the declared compute receipts' arguments and the
    coverage the client recorded from the source result's own total/cursor
    fields, never the answer or question text.
    """
    notes: list[str] = []
    for item in receipts:
        if not (isinstance(item, dict) and item.get("name") == TOOL_NAME
                and item.get("success") and item.get("result_kind") == "local_compute"):
            continue
        if item.get("ranking_held_back"):
            continue  # no figure was computed; the model re-read instead
        args = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
        wanted = args.get("receipt_indexes") or ([args["receipt_index"]]
                                                  if args.get("receipt_index") else [])
        sources = []
        for index in wanted:
            if isinstance(index, int) and 1 <= index <= len(receipts):
                sources.append(receipts[index - 1])
        if not wanted:
            sources = [r for r in receipts if isinstance(r, dict) and r.get("row_coverage")][-1:]
        covs = [s.get("row_coverage") for s in sources
                if isinstance(s, dict) and isinstance(s.get("row_coverage"), dict)]
        if covs:
            returned = sum(c.get("rows_returned") or 0 for c in covs)
            totals = [c["source_reported_total"] for c in covs
                      if c.get("source_reported_total") is not None]
            total = max(totals) if totals else None
            last_cursor = covs[-1].get("next_cursor")
            partial = ((total is not None and returned < total) or bool(last_cursor)
                       if len(covs) > 1 else bool(covs[0].get("partial")))
            ordered = covs[0].get("ordered_by_source")
            if (partial and len(covs) == 1 and isinstance(ordered, dict)
                    and args.get("field") == ordered.get("field")
                    and args.get("operation") in ("sort", "min", "max")):
                text = (f"Coverage: the hub returned {returned}"
                        + (f" of {total}" if total is not None else "")
                        + f" rows already ordered {ordered['direction']} by its own "
                        f"`{ordered['field']}` sort, so these are the leading rows of that "
                        "ordering, not an arbitrary subset; that the hub sorted before paging "
                        "was not independently verified.")
                if text not in notes:
                    notes.append(text)
            elif partial:
                text = (f"Coverage: figures above come from {returned}"
                        + (f" of {total}" if total is not None else "")
                        + f" rows returned by {sources[0].get('name')}; the remaining rows were not read.")
                if text not in notes:
                    notes.append(text)
        if sources:
            src_name = sources[0].get("name")
            failed = sum(1 for r in receipts if isinstance(r, dict) and r.get("name") == src_name
                         and not r.get("success") and isinstance(r.get("arguments"), dict)
                         and r["arguments"].get("cursor") not in (None, ""))
            if failed:
                text = (f"Paging: {failed} attempt(s) to read further pages of {src_name} "
                        "were refused or failed, so rows beyond those returned were not read.")
                if text not in notes:
                    notes.append(text)
        skipped = item.get("same_source_receipts_not_included")
        if skipped:
            text = ("Coverage: this computation did not include "
                    f"{len(skipped)} further page(s) of the same read that were returned "
                    "in this request, so a ranking may miss rows from them.")
            if text not in notes:
                notes.append(text)
        source = item.get("compute_source")
        if isinstance(source, dict) and source.get("operation") in ("sort", "min", "max") \
                and source.get("rows_path"):
            table = str(source["rows_path"]).split(".")[-1]
            mode = source.get("mode")
            mode_text = ", ".join(map(str, mode)) if isinstance(mode, list) else (str(mode) if mode else "")
            text = (f"Source table: `{table}` of {source.get('tool')}"
                    + (f" (mode {mode_text})" if mode_text else "") + ".")
            if text not in notes:
                notes.append(text)
    return " ".join(notes) if notes else None


_MEMORY_WORDS = re.compile(r"\b(memory|ram)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(not|no|nor|never|cannot|can't|doesn't|does not|isn't|aren't|without)\b",
                       re.IGNORECASE)
_PROXY_WORDS = re.compile(r"\b(proxy|correlat\w*|indication|indicator|approximat\w*|closest)\b", re.IGNORECASE)
_MEMORY_SOURCES = ("hub_get_memory_history", "hub_get_metrics")


def field_meaning_prose_note(answer: str, receipts: list[dict]) -> str | None:
    """Footnote when prose ties memory/RAM to a table the client marked as not memory.

    Structural trigger: a successful receipt carries a client field-meaning note
    (declared tool, returned field names). The check reads the MODEL's answer, never
    the question: a sentence naming memory/RAM with no negation is flagged. It adds
    the fact only; it never edits or removes the model's text.
    """
    if not answer or not any(r.get("field_meaning_fields") for r in receipts):
        return None
    clauses = re.split(r"(?<=[.!?;])\s+|\n+", answer.replace("\u2019", "'"))
    flagged = [s for s in clauses if _MEMORY_WORDS.search(s) and (
        (not _NEGATION.search(s) and "stateSize" in s) or _PROXY_WORDS.search(s))]
    if not flagged:
        return None
    fields = sorted({f for r in receipts for f in (r.get("field_meaning_fields") or [])})
    read = any(r.get("success") and r.get("name") in _MEMORY_SOURCES for r in receipts)
    return ("Field note: " + ", ".join(f"`{f}`" for f in fields)
            + " in the returned table are stored-state bytes or runtime measures; none is RAM or "
            "memory use, so the memory wording above is not supported by that table. "
            + ("Memory figures read this request come from " + "/".join(_MEMORY_SOURCES) + "."
               if read else "No memory source was read in this request."))


def partial_ranking_warning(source: dict, compute_args: dict, catalog: list) -> dict | None:
    """Warn when a ranking ran over an unsorted partial page the source could have sorted.

    Structural: the source receipt's recorded coverage and arguments, the compute
    call's declared operation/field, and the live tool schema's parameter names.
    It never reads the question; it only tells the model what the source offers.
    """
    if not isinstance(source, dict) or compute_args.get("operation") not in ("sort", "min", "max"):
        return None
    cov = source.get("row_coverage")
    if not isinstance(cov, dict) or not cov.get("partial") or cov.get("ordered_by_source"):
        return None
    args = source.get("arguments") if isinstance(source.get("arguments"), dict) else {}
    if any(k in args for k in _SORT_ARGS):
        return None
    tool = next((c for c in catalog or [] if isinstance(c, dict) and c.get("name") == source.get("name")), None)
    props = ((tool or {}).get("inputSchema") or {}).get("properties")
    key = next((k for k in _SORT_ARGS if isinstance(props, dict) and k in props), None)
    if key is None:
        return None
    field = compute_args.get("field")
    return {
        "source": "client note from this request's receipts and the live tool schema; not hub data",
        "rows_read": cov.get("rows_returned"), "source_reported_total": cov.get("source_reported_total"),
        "sort_parameter_offered": key,
        "use": (f"This {compute_args.get('operation')} covers only the first {cov.get('rows_returned')} "
                f"rows of {cov.get('source_reported_total')} in the source's default order, so it is not a "
                f"ranking of the whole source. {source.get('name')} offers a `{key}` parameter: re-read it once "
                f"with the same arguments plus {key}"
                + (f"=\"{field}\"" if isinstance(field, str) else "")
                + " (and a small limit if offered), and rank from those rows. If that read fails, say "
                "the ranking covers only the first rows."),
    }


def unrun_tool_note(answer: str, receipts: list[dict], tool_names) -> str | None:
    """Footnote naming catalog tools the answer mentions but never successfully ran.

    Compares the answer against the declared tool catalog and this request's
    receipts. It does not read the question and does not judge the wording: a
    mention may be advice or a false claim, so the note only states the fact that
    no successful read of that tool exists in this request.
    """
    if not answer or not tool_names:
        return None
    ran = {r.get("name") for r in receipts if isinstance(r, dict) and r.get("success")}
    mentioned = sorted(
        name for name in tool_names
        if isinstance(name, str) and name not in ran and name != TOOL_NAME
        and re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", answer))
    if not mentioned:
        return None
    return ("Not run in this request: " + ", ".join(mentioned)
            + ". No figure here was read from that tool; any number the text above "
              "attributes to it is not backed by a receipt.")


def unit_conversion_note(result: Any) -> dict | None:
    """Decimal MB and binary MiB for numeric fields whose key ends in KB.

    Keyed only on returned field names, so the model never has to convert by
    hand. Looks a few levels into the decoded result.
    """
    found: dict[str, dict] = {}
    queue: list[tuple[Any, int]] = [(_decode(result), 0)]
    while queue and len(found) < 6:
        node, level = queue.pop(0)
        node = _decode(node)
        if isinstance(node, dict) and level < 5:
            for key, value in node.items():
                if isinstance(key, str) and key.startswith("client_"):
                    continue
                if (isinstance(key, str) and key.endswith("KB") and isinstance(value, (int, float))
                        and not isinstance(value, bool)):
                    found.setdefault(key, {"value_KB": value,
                                           "MB_decimal": round(value / 1000, 3),
                                           "MiB_binary": round(value / 1024, 3)})
                elif isinstance(value, (dict, list, str)):
                    queue.append((value, level + 1))
        elif isinstance(node, list) and level < 5:
            queue.extend((child, level + 1) for child in node[:3])
    if not found:
        return None
    return {"source": "client conversion of returned KB fields; not hub data",
            "fields": found,
            "use": "Quote MB as the decimal figure (KB divided by 1,000) unless the person asked for MiB."}


_AGGREGATE_WORDS = re.compile(
    r"\b(total|sum|average|mean|median|most|least|highest|lowest|top|largest|smallest|"
    r"rank(?:ed|ing)?|count|in total|combined|maximum|minimum|oldest|newest|longest|shortest)\b", re.I)
_LARGE_NUMBER = re.compile(r"(?<![\w.-])\d{1,3}(?:,\d{3})+(?![\w-])|(?<![\w.-])\d+(?:\.\d+)?\s?(?:%|MB|KB|GB|W|kWh|bytes|h|hours|min)\b")
_ROW_COUNT = re.compile(r"\b\d+\s+(?:of\s+\d+\s+)?(?:devices|apps|rows|entries|sensors|lights|batteries|items)\b", re.I)


def draft_states_aggregate(text: str) -> bool:
    """True when the model's own draft appears to state a count, ranking, total or measurement.

    Applies to the model's draft, never the user's text. A plain list of names and states needs no
    compute-receipt round, so the extra nudge round is skipped for it.
    """
    body = re.sub(r"`[^`]*`", "", text or "")
    return bool(_AGGREGATE_WORDS.search(body) or _ROW_COUNT.search(body) or _LARGE_NUMBER.search(body))


_UNIT_MARK = {"C": re.compile(r"°\s?C\b|celsius|\"unit\"\s*:\s*\"°?C\"", re.I),
              "F": re.compile(r"°\s?F\b|fahrenheit|\"unit\"\s*:\s*\"°?F\"", re.I)}


def temperature_unit_note(answer: str, receipts: list) -> str:
    """Footnote when the answer names a temperature unit that no tool result states."""
    said = [u for u in ("C", "F") if re.search(rf"°\s?{u}\b", answer or "")]
    if not said:
        return ""
    stored = " ".join(str(r.get("response") or "") for r in receipts if isinstance(r, dict))
    unsupported = [u for u in said if not _UNIT_MARK[u].search(stored)]
    if not unsupported:
        return ""
    return ("Unit note: no tool result this request states a temperature unit, so the "
            f"{'/'.join('°' + u for u in unsupported)} label above is not read from the hub; "
            "treat the numbers as degrees in the hub's configured scale.")


_LIST_FILTER_ARGS = ("changedSince", "stateFilter", "labelFilter", "roomFilter", "capabilityFilter",
                     "deviceIds", "attributeNames")


def filter_scope_note(name: str, args: dict) -> dict | None:
    """Tell the model that a filtered device list's total/count refers to the filtered set.

    Built only from the call's own arguments; it adds no hub data.
    """
    if name != "hub_list_devices" or not isinstance(args, dict):
        return None
    applied = {k: args[k] for k in _LIST_FILTER_ARGS if k in args and k != "attributeNames"}
    if not applied:
        return None
    return {"source": "client note from this call's arguments; not hub data",
            "filters_applied": applied,
            "meaning": "total, count and hasMore in this result describe only the devices that match "
                       "these filters, not the whole inventory. Do not report that number as how many "
                       "devices exist."}
