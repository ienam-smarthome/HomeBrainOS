"""Read-only differential inspection of two actual native Rule Machine settings.

This is an *evidence collector*, not a writer. A unique typed date field
identified from a known dated trigger versus a known undated trigger is one
necessary fact for a future native one-shot authoring contract. It does not
prove the native create API accepts the same placeholder name or value, nor
that the rule will fire once. NEVER activate a write based on this report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

# An explicit integration gate: the runtime native create adapter, approved
# backup/confirmation sequence and post-write verifier are NOT implemented.
# Evidence discovery alone never enables a native one-shot write.
NATIVE_ONESHOT_ENABLED = False

_DATE_ONLY = re.compile(r"(\d{4})-(\d{2})-(\d{2})\Z")
_EXPECTED = {
    "tCapab1": ("enum", "Certain Time (and optional date)"),
    "time1": ("enum", "A specific time"),
    "atTime1": ("time", None),
}
_KNOWN = frozenset({
    "tCapab1", "time1", "atTime1", "date1", "origLabel",
    "actType.1", "actSubType.1", "onOff.1", "onOffSwitch.1",
})


@dataclass(frozen=True)
class DateFieldProbe:
    date_flag: dict[str, str] | None
    date_value: dict[str, str] | None
    gaps: tuple[str, ...]

    @property
    def write_ready(self) -> bool:
        """Only a live, separately confirmed writer/readback can grant writes."""
        return False


def _settings(document: Any) -> tuple[dict[str, dict[str, Any]] | None, int | None]:
    if not isinstance(document, dict) or document.get("success") is False:
        return None, None
    ident = document.get("rule_id")
    if type(ident) is not int or ident <= 0:
        return None, None
    rows = document.get("settings")
    if not isinstance(rows, list) or not rows:
        return None, None
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("name"), str)
            or not isinstance(row.get("type"), str)
            or row.get("redacted") is True
            or row["name"] in found
        ):
            return None, None
        found[row["name"]] = row
    return found, ident


def inspect_native_one_shot_date_field(
    *, dated_read: Any, undated_read: Any,
) -> DateFieldProbe:
    """Identify a *candidate* dated field; never imply executable authority.

    Caller must independently establish these are actual, correctly scoped
    read-only results from the *same hub*, dated with the date checkbox on
    and undated without it. This does not infer parent, backup, permissions,
    form selector placeholders or the native create/write contract.
    """
    dated, dated_id = _settings(dated_read)
    undated, undated_id = _settings(undated_read)
    if dated is None or undated is None or dated_id == undated_id:
        return DateFieldProbe(None, None, ("native_oneshot_date_field_unverified",))

    for name, (kind, expected) in _EXPECTED.items():
        for record in (dated, undated):
            row = record.get(name)
            if row is None or row.get("type") != kind:
                return DateFieldProbe(None, None, ("native_oneshot_date_field_unverified",))
            if expected is not None and row.get("value") != expected:
                return DateFieldProbe(None, None, ("native_oneshot_date_field_unverified",))
    # The two controls must be of the *same* trigger class, and the dated
    # sample must have a visible explicit date flag. A "date1" name alone
    # without a true value does not prove the checkbox was selected.
    flag = dated.get("date1")
    baseline_flag = undated.get("date1")
    if not (
        isinstance(flag, dict)
        and flag.get("type") == "bool"
        and flag.get("value") in (True, "true")
        and (baseline_flag is None
             or (baseline_flag.get("type") == "bool"
                 and baseline_flag.get("value") in (False, "false", None, "")))
    ):
        return DateFieldProbe(None, None, ("native_oneshot_date_field_unverified",))
    # Source sample is only a typed form setting; never guess a date field
    # from similarly named action selectors or the ISO date in a rule label.
    candidates: list[dict[str, str]] = []
    for name, row in dated.items():
        if name in _KNOWN or not name.endswith("1"):
            continue
        if row.get("type") not in {"date", "text"}:
            continue
        value = row.get("value")
        match = _DATE_ONLY.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            continue
        try:
            date.fromisoformat(value)
        except ValueError:
            continue
        before = undated.get(name)
        if before is not None and before.get("value") not in (None, ""):
            continue
        candidates.append({
            "name": name[:-1] + "#",
            "type": str(row["type"]),
            "fmt": "YYYY-MM-DD",
        })
    if len(candidates) != 1:
        return DateFieldProbe(None, None, ("native_oneshot_date_field_unverified",))
    return DateFieldProbe(
        date_flag={"name": "date#", "type": "bool"},
        date_value=candidates[0],
        gaps=("native_oneshot_create_placeholder_and_readback_unverified",),
    )


__all__ = ["NATIVE_ONESHOT_ENABLED", "DateFieldProbe", "inspect_native_one_shot_date_field"]
