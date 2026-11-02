"""Read-only Rule Machine inventory and native-parent evidence.

App/rule lists establish membership and identity, not execution or a
complete native Rule Machine action tree. The class-type join uses exact
Hubitat source IDs; it never infers a parent by app counts or labels.
"""
from __future__ import annotations

import re
import time
from typing import Any

from mcp_client import tool_succeeded

_ONE_TIME = re.compile(r"\(One-time \d{4}-\d{2}-\d{2} \d{2}:\d{2}\)$", re.I)
_LOOKUP = re.compile(r"\b(?:list|find|identify|enumerate|show|locate|which|existing)\b", re.I)
_TOPIC = re.compile(r"\b(?:rule machine|rules?|one.time|one.off)\b", re.I)
_OBJECT = re.compile(r"\b(?:parent(?:\s+app|\s+id)?|one.time|one.off|inventory|rules?\s+list)\b", re.I)
_DEEP = re.compile(
    r"\b(?:why|caused|triggered it|actually (?:run|executed)|"
    r"nested\s+if|delay cancellation|historical\s+off)\b", re.I,
)
_LITERAL_ID = re.compile(r"\b(?:rule|app)\s*(?:id|#)?\s*[:#]?\s*\d{3,8}\b", re.I)
_ID = re.compile(r"[1-9]\d{0,8}")


def is_native_rule_inventory_question(question: str) -> bool:
    """A factual inventory lookup, not a named-rule logic/execution audit."""
    text = str(question or "")
    return bool(_LOOKUP.search(text) and _TOPIC.search(text)
                and _OBJECT.search(text) and not _DEEP.search(text)
                and not _LITERAL_ID.search(text))


def _id(value: Any) -> str | None:
    if type(value) not in (str, int) or not _ID.fullmatch(str(value)):
        return None
    return str(value)


def _collection(data: Any, key: str, *, total_field: str | None = None):
    """Return rows and completeness; never infer global absence from a page."""
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        return [], False
    raw = data[key]
    if len(raw) > 5000 or any(not isinstance(x, dict) for x in raw):
        return [], False
    complete = (
        type(data.get("count")) is int
        and data["count"] == len(raw)
        and not data.get("nextCursor")
        and data.get("truncated") is not True
    )
    if total_field is not None:
        complete = complete and (
            type(data.get(total_field)) is int
            and data[total_field] == len(raw)
        )
    if data.get("filter") not in (None, "all"):
        complete = False
    return raw, complete


def _label(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("label") or "").strip()


def project_rule_inventory(instances: Any, types: Any, rules: Any) -> dict[str, Any]:
    inst, inst_complete = _collection(instances, "apps", total_field="totalOnHub")
    type_rows, types_complete = _collection(types, "apps")
    rule_rows, rules_complete = _collection(rules, "rules")
    native_types = {
        _id(row.get("id")) for row in type_rows
        if row.get("namespace") == "hubitat"
        and row.get("name") == "Rule Machine"
        and _id(row.get("id"))
    }
    parents = []
    possible = []
    for row in inst:
        if row.get("type") != "Rule Machine" or _label(row) != "Rule Machine":
            continue
        app_id = _id(row.get("id"))
        if not app_id or row.get("parentId") not in (None, ""):
            continue
        app_type = _id(row.get("appTypeId"))
        if app_type in native_types:
            parents.append({"appId": app_id, "appTypeId": app_type,
                            "namespace": "hubitat", "name": "Rule Machine"})
        else:
            possible.append({"appId": app_id, "typeProof": "unverified"})

    matches: dict[str, dict[str, Any]] = {}
    for source, rows in (("hub_list_rules", rule_rows),
                         ("hub_list_apps", inst)):
        for row in rows:
            name = _label(row)
            app_id = _id(row.get("id") or row.get("appId"))
            if app_id is None or len(name) > 200 or not _ONE_TIME.search(name):
                continue
            if source == "hub_list_apps" and not (
                str(row.get("type") or "").startswith("Rule-")
                or _id(row.get("parentId")) in {
                    p["appId"] for p in parents
                }
            ):
                continue
            item = matches.setdefault(app_id, {
                "appId": app_id, "name": name, "sourceKinds": [],
            })
            if item["name"] != name:
                item["nameConflict"] = True
            item["sourceKinds"].append(source)
            parent_id = _id(row.get("parentId"))
            if parent_id and source == "hub_list_apps":
                item["parentId"] = parent_id
    matching = [x for x in matches.values() if not x.get("nameConflict")]
    matching.sort(key=lambda x: (x["name"], int(x["appId"])))
    return {
        "source": "typed hub_list_apps instances/types + hub_list_rules",
        "parents": parents[:20],
        "candidateParents": possible[:20],
        "parentIdentityComplete": inst_complete and types_complete,
        "oneTimeRules": matching[:30],
        "oneTimeMatchCount": len(matching),
        "ruleListComplete": rules_complete,
        "appListComplete": inst_complete,
        "typesListComplete": types_complete,
        "inventoryConflicts": [
            {"appId": x["appId"], "issue": "name-conflict"}
            for x in matches.values() if x.get("nameConflict")
        ][:10],
    }


def render_inventory(data: dict[str, Any]) -> str:
    lines = ["**Rule Machine inventory — read-only**", ""]
    parents = data["parents"]
    if parents:
        lines.append(
            "Verified native Rule Machine parent app"
            + ("s" if len(parents) != 1 else "") + ": "
            + ", ".join("ID **" + p["appId"] + "**" for p in parents) + "."
        )
    elif data["candidateParents"]:
        ids = ", ".join(x["appId"] for x in data["candidateParents"])
        lines.append(
            "Rule Machine-named app instance ID(s) "
            + ids + " were returned, but their built-in app-type namespace "
            "was not verified. The native parent ID remains unresolved."
        )
    else:
        lines.append(
            "No native parent ID verified"
            + (" in the complete returned app/type inventory."
               if data["parentIdentityComplete"] else
               "; source coverage is incomplete.")
        )
    lines.append("")
    matches = data["oneTimeRules"]
    if matches:
        lines.append("Existing one-time rule names and IDs in the returned inventory:")
        for item in matches:
            suffix = (f" (recorded parent ID {item['parentId']})"
                      if item.get("parentId") else "")
            lines.append(f"- **{item['name']}** — ID {item['appId']}{suffix}")
        if len(matches) < data["oneTimeMatchCount"]:
            lines.append(
                f"Displaying {len(matches)} of {data['oneTimeMatchCount']} "
                "matching rows."
            )
        if not data["ruleListComplete"] or not data["appListComplete"]:
            lines.append("Not all rules are proven covered by these reads.")
    elif data["ruleListComplete"] and data["appListComplete"]:
        lines.append("No exact one-time suffix matched in the complete "
                     "returned rule/app listings.")
    else:
        lines.append(
            "No matching one-time rule was verified in the available "
            "listings; incomplete reads do not establish absence."
        )
    if data["inventoryConflicts"]:
        lines.append("Some app/rule source names conflicted and were excluded.")
    lines.append("")
    lines.append(
        "These are saved inventory facts, not proof of execution, one-shot "
        "scheduling or post-execution cleanup. No Hubitat rule/device changed."
    )
    return "\n".join(lines)


async def read_native_rule_inventory(
    mcp: Any, recorder: Any, *, available_names: set[str] | frozenset[str],
) -> tuple[str, dict[str, Any]]:
    """Three bounded, explicitly read-only MCP gateway calls."""
    async def get(gateway: str, tool: str, args: dict[str, Any]) -> Any:
        if gateway not in available_names:
            return None
        request = {"tool": tool, "args": args}
        start = time.monotonic()
        try:
            result = await mcp.call_tool(gateway, request)
            data = result.data if (tool_succeeded(result)
                                  and isinstance(result.data, dict)) else None
        except Exception:
            data = None
        recorder.record(
            gateway, request, success=data is not None,
            elapsed_ms=round((time.monotonic() - start) * 1000),
            summary=("Rule inventory source read: " if data is not None
                     else "Rule inventory source unavailable: ") + tool,
            supports_live_claim=False,
            evidence_kind="native_rule_inventory_source",
            effect="read", mutates=False,
        )
        return data

    inst = await get("hub_read_apps_code", "hub_list_apps",
                     {"scope": "instances"})
    types = await get("hub_read_apps_code", "hub_list_apps",
                      {"scope": "types"})
    rules = await get("hub_read_rules", "hub_list_rules", {})
    projection = project_rule_inventory(inst, types, rules)
    recorder.record(
        "homebrain_native_rule_inventory", {},
        success=bool(projection["parents"] or projection["oneTimeRules"]
                     or projection["parentIdentityComplete"]
                     or projection["ruleListComplete"]),
        elapsed_ms=0,
        summary="Typed Rule Machine parent/inventory source projection",
        evidence_kind="typed_native_rule_inventory",
        supports_live_claim=True, effect="read", mutates=False,
        details=projection,
    )
    return render_inventory(projection), projection
