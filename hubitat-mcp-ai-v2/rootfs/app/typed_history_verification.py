"""Typed, source-derived final answer for explicit exhaustive native event queries.

The model chooses the tools and can reason about causes; this *narrow* contract
prevents a claimed complete timestamp/command listing from contradicting a
successful original device-events receipt. Does not read tools, run a model,
write home state or invent any missing events. Unverifiable cases fail closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from temporal_receipt_fidelity import _native_payload, _safe_event

_MAX_NATIVE_ROWS = 120
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SAFE_ACTOR = re.compile(r"^[A-Za-z][A-Za-z0-9 ()_.-]{0,55}$")
_SCOPE = re.compile(
    r"\b(?:all|every|each)\s+(?:of\s+the\s+|the\s+)?"
    r"(?:returned|recorded|observed|matching)\b", re.I,
)
_EVENT_REQUEST = re.compile(
    r"\b(?:events?|state\s+changes?|transitions?|"
    r"on\s*[/&-]\s*off|off\s*[/&-]\s*on)\b", re.I,
)
_WRITE_LEAD = re.compile(
    r"^\s*(?:turn|switch|set|delete|create|install|change|disable|"
    r"enable|block|unlock|lock|pause|resume)\b", re.I,
)
_DURATION = re.compile(
    r"\b(?:past|last|previous)\s+"
    r"(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve)\s+hours?\b", re.I,
)
_WORD_COUNT = {
    "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,
    "seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,
}
# Explicit state-domain words only. A generic "every event" request may
# contain IP addresses, arbitrary descriptions and private identifiers:
# don't project it as a state timeline.
_FIELD_HINTS = (
    ("switch", re.compile(r"\b(?:switch|on\s*[/&-]\s*off|"
                         r"off\s*[/&-]\s*on|switched\s+(?:on|off))\b", re.I)),
    ("thermostatOperatingState", re.compile(
        r"\b(?:thermostatoperatingstate|heating\s+state|heating\s+to\s+idle|"
        r"heating\s*[/&-]\s*idle)\b", re.I)),
    ("motion", re.compile(r"\b(?:motion|active\s*[/&-]\s*inactive)\b", re.I)),
    ("contact", re.compile(r"\b(?:contact|open\s*[/&-]\s*closed)\b", re.I)),
    ("lock", re.compile(r"\b(?:lock\s+state|locked\s*[/&-]\s*unlocked)\b", re.I)),
)
_SAFE_VALUES = {
    "switch": frozenset(("on","off")),
    "thermostatOperatingState": frozenset(("heating","idle","cooling","pending heat","pending cool")),
    "motion": frozenset(("active","inactive")),
    "contact": frozenset(("open","closed")),
    "lock": frozenset(("locked","unlocked")),
}


def _target_field(question: str) -> str | None:
    if (not isinstance(question, str)
            or not _SCOPE.search(question)
            or not _EVENT_REQUEST.search(question)
            or _WRITE_LEAD.search(question)):
        return None
    matched = [field for field, rx in _FIELD_HINTS if rx.search(question)]
    return matched[0] if len(matched) == 1 else None


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 0 < len(value) <= 48:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None


def _safe_id(value: Any) -> str | None:
    if type(value) is int and 0 < value < 1000000000:
        return str(value)
    if (isinstance(value, str) and value.isascii() and value.isdecimal()
            and 0 < len(value) <= 9 and int(value) > 0):
        return str(int(value))
    return None


def _actor(value: Any) -> str:
    if not isinstance(value, dict):
        return "issuer not identified in this row"
    app_id = _safe_id(value.get("appId"))
    device_id = _safe_id(value.get("deviceId"))
    identifier = ("app " + app_id if app_id else
                  "device " + device_id if device_id else "issuer not identified")
    name = value.get("name")
    if isinstance(name, str) and _SAFE_ACTOR.fullmatch(name) and not re.search(
        r"passw|secret|token|credential|auth|access.key|pin|code", name, re.I,
    ):
        return identifier + " (" + name + ")"
    return identifier


def _render_interval(a: datetime, b: datetime) -> str:
    seconds = (b-a).total_seconds()
    if seconds < 0:
        raise ValueError("Out-of-order returned timestamps")
    if seconds == 0:
        return "Same reported instant; order unverified"
    hours, rem = divmod(seconds, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{int(hours)}h {int(minutes)}m {sec:.3f}s"
    if minutes:
        return f"{int(minutes)}m {sec:.3f}s"
    return f"{sec:.3f}s"


def _unverified(reason: str, field: str) -> dict:
    # Never release an inaccurate exhaustive source chronology when required
    # original receipt scope is absent, ambiguous, malformed, or truncated.
    return {
        "status": "unverified",
        "event_field": field,
        "reason": reason,
        "source_event_rows": 0,
        "answer": (
            "I cannot verify an exhaustive returned-event timeline from the "
            "successful original native event receipts in this request. "
            "No complete sequence, command inventory, cause or absence is "
            "asserted. The PRIVATE Technical JSON retains the actual tool "
            "results; a focused read-only unfiltered device-event query may "
            "provide a verifiable result."
        ),
    }


def verify_and_project_history(
    question: str, draft_answer: str, receipts: list[dict]
) -> dict:
    """Return a verified, scoped ledger or fail closed for exhaustive requests.

    Other question families, including causal/non-enumerative asks and all
    writes, remain fully model-led. This deterministic source projection is
    ONLY for a user's explicit request for ALL RETURNED events.
    """
    field = _target_field(question)
    if field is None:
        return {"status":"not_applicable", "answer":draft_answer}
    if not isinstance(receipts, list):
        return _unverified("invalid_receipts",field)
    candidates = [r for r in receipts if isinstance(r,dict)
                  and r.get("name")=="hub_list_device_events"]
    # No combination of different read scopes, filters, devices or overlapping
    # windows is silently treated as a single complete timeline.
    if len(candidates)!=1 or candidates[0].get("success") is not True:
        return _unverified("no_unique_successful_native_event_receipt",field)
    receipt = candidates[0]
    args=receipt.get("arguments")
    if not isinstance(args,dict):
        return _unverified("missing_read_arguments",field)
    original = _native_payload(receipt)
    if not isinstance(original,dict) or not isinstance(original.get("events"),list):
        return _unverified("native_rows_unavailable",field)
    rows=original["events"]
    if len(rows)>_MAX_NATIVE_ROWS:
        return _unverified("returned_rows_exceed_safe_complete_projection_cap",field)
    for value in (original.get("count"),):
        if value is not None and (type(value) is not int or value!=len(rows)):
            return _unverified("original_row_count_mismatch",field)
    if str(original.get("deviceId",""))!=str(args.get("deviceId","")):
        return _unverified("source_device_identity_mismatch",field)
    filtered=original.get("attributeFilter")
    if filtered is None:
        filtered=args.get("attribute")
    if filtered not in (None,field):
        return _unverified("read_filter_excludes_requested_state",field)
    asks_commands=bool(re.search(r"\bcommands?\b|\bissuers?\b",question,re.I))
    if asks_commands and filtered is not None:
        return _unverified("filtered_history_cannot_enumerate_commands",field)
    hours= _DURATION.search(question)
    requested_hours= _WORD_COUNT.get(hours.group(1).lower()) if hours and not hours.group(1).isdigit() else int(hours.group(1)) if hours else None
    if (requested_hours is not None and
            (str(args.get("hoursBack"))!=str(requested_hours)
             or str(original.get("hoursBack",args.get("hoursBack")))!=str(requested_hours))):
        return _unverified("requested_history_duration_not_read",field)
    since=original.get("sinceTimestamp")
    if since is not None and _date(since) is None:
        return _unverified("requested_since_timestamp_unparseable",field)
    # A backend may provide separate source scope about unreturned rows;
    # if it explicitly contradicts the parsed data, stop rather than fudge.
    try:
        outer=__import__("json").loads(str(receipt.get("response","")))
    except (ValueError,TypeError):
        return _unverified("invalid_original_receipt_envelope",field)
    if not isinstance(outer,dict):
        return _unverified("invalid_original_receipt_envelope",field)
    head=outer.get("client_claim_evidence_headline")
    if isinstance(head,dict) and head.get("returned_row_count") is not None:
        if type(head["returned_row_count"]) is not int or head["returned_row_count"]!=len(rows):
            return _unverified("envelope_row_count_mismatch",field)
    if isinstance(head,dict) and head.get("row_limit_reached") is True:
        return _unverified("source_response_page_was_capped",field)
    # Validate *every* selected state row and every command, not only those
    # the model mentioned. Do not reveal arbitrary attributes or IP addresses.
    states,commands,other_counts=[],[],{}
    for i,raw in enumerate(rows):
        if not isinstance(raw,dict):
            return _unverified("malformed_original_event_row",field)
        name=raw.get("name")
        if not isinstance(name,str) or _NAME.fullmatch(name) is None:
            # Arbitrary event names can be private; ignore only irrelevant
            # rows, never silently omit selected-state or command records.
            return _unverified("unsafe_original_event_name",field)
        if name==field:
            safe=_safe_event(raw,1)
            parsed=_date(raw.get("date"))
            value=raw.get("value")
            if (not safe or parsed is None or
                    not isinstance(value,str) or
                    value.lower() not in _SAFE_VALUES[field]):
                return _unverified("state_row_unverifiable",field)
            states.append((parsed,raw.get("date"),value.lower(),raw.get("producedBy")))
        elif name.startswith("command-") or raw.get("type")=="command":
            stamp=_date(raw.get("date"))
            if stamp is None:
                return _unverified("command_timestamp_unverifiable",field)
            commands.append((stamp,raw["date"],name,raw.get("producedBy")))
        else:
            other_counts[name]=other_counts.get(name,0)+1
    states.sort(key=lambda x:x[0])
    commands.sort(key=lambda x:x[0])
    lines = [
        f"### Verified returned-event ledger — {field}",
        "",
        "This table is generated from the original successful native event "
        "receipt, **not from the model's event enumeration**. It describes "
        "only the rows returned by that query, not every event that "
        "necessarily occurred or was stored.",
        "",
        f"Device ID: `{_safe_id(args.get('deviceId')) or 'unverified'}`. "
        f"Native query lookback: `{args.get('hoursBack', 'unspecified')}` hour(s).",
    ]
    if since:
        lines.append(f"Requested source start (as returned): `{since}`.")
    if rows:
        valid_dates=[_date(r.get("date")) for r in rows]
        valid_stamps=[r.get("date") for r in rows]
        if any(d is None for d in valid_dates):
            return _unverified("some_original_rows_have_invalid_timestamps",field)
        positions=sorted(range(len(rows)),key=lambda i:valid_dates[i])
        lines.append(f"Earliest / latest returned row: `{valid_stamps[positions[0]]}` / `{valid_stamps[positions[-1]]}`.")
    lines += ["",f"**{len(states)} returned {field} reports** (offset-aware timestamps, ordered by instant):",
              "", "| # | Timestamp (as returned) | Reported value | Since previous returned report | Reporter |",
              "|---:|---|---|---|---|"]
    for i,(stamp,raw_stamp,value,reporter) in enumerate(states):
        gap="—" if i==0 else _render_interval(states[i-1][0],stamp)
        lines.append(f"| {i+1} | `{raw_stamp}` | **{value.upper() if field=='switch' else value}** | {gap} | {_actor(reporter)} |")
    lines += ["",f"**{len(commands)} returned command rows** (recorded issuers, not proven causes):",""]
    if commands:
        lines += ["| Timestamp (as returned) | Command event | Recorded issuer |",
                  "|---|---|---|"]
        for _,raw_stamp,name,issuer in commands:
            lines.append(f"| `{raw_stamp}` | `{name}` | {_actor(issuer)} |")
    else:
        lines.append("No command rows **in this returned receipt**; this does not exclude commands elsewhere.")
    if other_counts:
        # Never include raw values for unrelated history (including IPs).
        totals=", ".join(f"`{k}`: {v}" for k,v in sorted(other_counts.items()))
        lines += ["",f"Other returned event-name counts (values not reproduced): {totals}."]
    lines += ["",
       "**Evidence limits:** Rows are discrete reports. A state reporter or "
       "notified listener is not automatically a command issuer; a command "
       "issuer does not establish the controller's internal reason. Commands "
       "logged AFTER a state event cannot be presumed to have initiated that "
       "earlier event. The unfiltered/filtered returned result cannot prove "
       "unseen events absent, continuous state between reports, or complete "
       "historical retention. Increasing the lookback does not guarantee "
       "complete history."]
    cited=sum(1 for _,stamp,_,_ in states if stamp in str(draft_answer))
    return {
        "status":"source_ledger_used",
        "reason":"exact_exhaustive_returned_event_enumeration",
        "event_field":field,
        "source_event_rows":len(rows),
        "selected_state_rows":len(states),
        "source_command_rows":len(commands),
        "state_rows_cited_verbatim_in_model_draft":cited,
        "answer":"\n".join(lines),
    }
