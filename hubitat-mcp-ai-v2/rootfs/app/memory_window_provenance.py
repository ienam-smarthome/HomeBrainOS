"""Exact UTC window checks for native memory samples with MM-DD timestamps.

Original client-clock receipt anchors the requested period. Native dates lack
a year and zone, so year rollover is resolved against the client instant and
configured hub timezone; this is labelled interpreted, not source-attested.
Samples are discrete: a returned gap is not continuous telemetry or proof
that absent intermediate samples were never generated.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re

from investigation_source_ledger import _response


_WINDOW = re.compile(
    r"\b(?:last|past|preceding|previous|prior)\s+(\d{1,4})[\s-]*"
    r"(minutes?|hours?)\b", re.I,
)
_TABLE_TIMESTAMP = re.compile(
    r"\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|"
)
_MAX_ROWS = 1200


def memory_history_window_index(
    question: str, receipts: list[dict], timezone_name: str | None,
) -> dict | None:
    if not isinstance(question, str):
        return None
    match = _WINDOW.search(question)
    if match is None or not any(
        word in question.lower() for word in ("memory", "ram", "cpu")
    ):
        return None
    minutes = int(match.group(1)) * (60 if match.group(2).lower().startswith("hour") else 1)
    if not 1 <= minutes <= 1440:
        return None
    try:
        zone = ZoneInfo(timezone_name or "Europe/London")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")

    now = None
    entries = None
    for receipt in receipts[:24]:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("operation_executed") is False
                and receipt.get("name") != "homebrain_read_clock"):
            continue
        name = receipt.get("name")
        _, data = _response(receipt)
        if not isinstance(data, dict):
            continue
        if name == "homebrain_read_clock":
            clock = data.get("local_clock")
            if not isinstance(clock, dict):
                continue
            raw = clock.get("client_now_utc")
            if not isinstance(raw, str):
                continue
            try:
                stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if stamp.tzinfo is not None:
                now = stamp.astimezone(timezone.utc)
        elif name == "hub_get_memory_history" and isinstance(data.get("entries"), list):
            entries = data["entries"][:_MAX_ROWS]
    if now is None or entries is None:
        return None
    start = now - timedelta(minutes=minutes)
    decoded: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        raw = item.get("timestamp")
        if not isinstance(raw, str) or not re.fullmatch(
            r"\d{2}-\d{2} \d{2}:\d{2}:\d{2}", raw
        ):
            continue
        # Infer year closest to the client clock without future-dating a
        # historical sample. Do not mistake the native MM-DD as ISO-year.
        candidates = []
        for yr in (now.year, now.year - 1):
            try:
                dt = datetime.strptime(f"{yr}-{raw}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            utc = dt.replace(tzinfo=zone).astimezone(timezone.utc)
            if utc <= now + timedelta(minutes=1):
                candidates.append(utc)
        if not candidates:
            continue
        instant = max(candidates)
        kb = item.get("freeMemoryKB")
        if type(kb) not in (int, float) or not 0 <= kb < 10**11:
            continue
        decoded.append({"timestamp": instant, "freeMemoryKB": kb})
    decoded.sort(key=lambda x: x["timestamp"])
    inside = [x for x in decoded if start <= x["timestamp"] <= now]
    gaps = [
        (b["timestamp"]-a["timestamp"]).total_seconds()
        for a, b in zip(inside, inside[1:])
    ]
    return {
        "requested_minutes": minutes,
        "client_now_utc": now.isoformat(),
        "window_start_utc": start.isoformat(),
        "in_window_sample_count": len(inside),
        "out_of_window_sample_count": len(decoded)-len(inside),
        "total_parsed_original_samples": len(decoded),
        "earliest_original_sample_utc": (
            decoded[0]["timestamp"].isoformat() if decoded else None
        ),
        "latest_original_sample_utc": (
            decoded[-1]["timestamp"].isoformat() if decoded else None
        ),
        "max_returned_in_window_gap_seconds": max(gaps, default=None),
        "native_MM_DD_year_and_zone_interpreted": True,
        "continuous_memory_coverage_proven": False,
        "unreturned_or_unobserved_intermediate_samples_absent_proven": False,
        "_in_window": inside,
        "_out_of_window": [x for x in decoded if x not in inside],
    }


def public_memory_window_scope(index: dict) -> dict:
    """Safe bounded numeric/clock model-navigation map, no raw source labels."""
    return {
        key: value for key, value in index.items()
        if not key.startswith("_")
    }


def verify_memory_window_publication(
    question: str, answer: str, receipts: list[dict], timezone_name: str | None,
) -> dict:
    index = memory_history_window_index(question, receipts, timezone_name)
    if index is None or not isinstance(answer, str):
        return {"status": "not_applicable", "reason": None, "answer": answer}
    # Only a date-specific table row advertised as a sample is checked.
    # Unrelated prose that discusses an older sample is not rewritten.
    stripped = answer.replace("‑", "-").replace("–", "-").replace("−", "-")
    lower = datetime.fromisoformat(index["window_start_utc"])
    upper = datetime.fromisoformat(index["client_now_utc"])
    outside = []
    for row in stripped.splitlines():
        match = _TABLE_TIMESTAMP.search(row)
        if not match:
            continue
        try:
            local = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        try:
            zone = ZoneInfo(timezone_name or "Europe/London")
        except (ZoneInfoNotFoundError, ValueError):
            zone = ZoneInfo("UTC")
        instant = local.replace(tzinfo=zone).astimezone(timezone.utc)
        if instant < lower or instant > upper:
            outside.append(instant)
    if not outside:
        return {
            "status": "bounded_window_index_available",
            "reason": None, "answer": answer,
            "scope": public_memory_window_scope(index),
        }

    lines = [
        "**Source-derived memory samples inside the requested window only.**",
        f"Requested UTC interval: {index['window_start_utc']} to "
        f"{index['client_now_utc']}.",
        f"Returned {index['in_window_sample_count']} qualifying samples; "
        f"{index['out_of_window_sample_count']} parsed samples lie outside "
        "this window. All are discrete reports, not continuous coverage.",
        "| Interpreted UTC sample time | freeMemoryKB |",
        "|---|---:|",
    ]
    for sample in index["_in_window"][:25]:
        lines.append(
            f"| {sample['timestamp'].isoformat()} | "
            f"{sample['freeMemoryKB']:g} |"
        )
    if len(index["_in_window"]) > 25:
        lines.append("Further in-window samples are omitted from this bounded display.")
    lines.append(
        "Native MM-DD timestamps were interpreted using the configured hub "
        "timezone and client year; the source does not include an independent "
        "year/timezone attestation. Gaps between reports remain unobserved."
    )
    return {
        "status": "unsafe",
        "reason": "published_sample_outside_requested_utc_window",
        "answer": "\n".join(lines),
        "scope": public_memory_window_scope(index),
    }
