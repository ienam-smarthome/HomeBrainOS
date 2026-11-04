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
from owned_device_inventory_source import is_explicit_owned_device_inventory_request
from native_rule_readiness_source import is_native_rule_readiness_question

_ONE_TIME = re.compile(r"\(One-time \d{4}-\d{2}-\d{2} \d{2}:\d{2}\)$", re.I)
_LOOKUP = re.compile(r"\b(?:list|find|identify|enumerate|show|locate|which|existing)\b", re.I)
_TOPIC = re.compile(r"\b(?:rule machine|rules?|one.time|one.off)\b", re.I)
_OBJECT = re.compile(r"\b(?:parent(?:\s+app|\s+id)?|one.time|one.off|inventory|rules?\s+list)\b", re.I)
# Only execution/causality needs a deep rule audit. A request to report
# *why source identity is unverified* is still a typed inventory objective,
# not an investigation into a rule firing. Generic "why" previously
# diverted these requests to the model/Groovy source route.
_DEEP = re.compile(
    r"\b(?:caused|nested\s+if|delay cancellation|historical\s+off|"
    r"triggered\s+(?:it|them|this\s+rule)|actually\s+(?:run|executed)|"
    r"(?:why|how|what)\b[^.!?\n]{0,120}\b(?:"
    r"turn(?:ed|ing)?\s+(?:on|off)|switch(?:ed|ing)?\s+(?:on|off)|"
    r"execut(?:e|ed|ing)|fired?|ran|run|trigger(?:ed|ing)?|"
    r"caus(?:e|ed|ing)|cancel(?:led|ed)|disabl(?:ed|ing)|"
    r"stopp?ed|fail(?:ed)?\s+to\s+(?:run|execute)"
    r")\b)"
    , re.I,
)
_LITERAL_ID = re.compile(r"\b(?:rule|app)\s*(?:id|#)?\s*[:#]?\s*\d{3,8}\b", re.I)
_ID = re.compile(r"[1-9]\d{0,8}")


def is_native_rule_inventory_question(question: str) -> bool:
    """A factual inventory lookup, not a named-rule logic/execution audit."""
    text = str(question or "")
    if is_explicit_owned_device_inventory_request(text):
        return False  # quoted Rule Machine exclusions are not the user objective
    if is_native_rule_readiness_question(text):
        return False  # backup inventory is not a Rule Machine parent/rule inventory
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


def _native_parent_from_summary(
    summary: Any, *, candidate_id: str, candidate_type_id: str | None,
) -> tuple[dict[str, Any] | None, str]:
    """Only source-returned typed native app identity can prove parentage.

    The upstream summary=true read returns /installedapp/json/{id}; some
    firmware returns only id/name/type/user. That cannot prove namespace.
    """
    if not isinstance(summary, dict) or summary.get("success") is not True:
        return None, "native-app-summary-unavailable"
    root = summary.get("app") if isinstance(summary.get("app"), dict) else summary
    if _id(root.get("id")) != candidate_id:
        return None, "native-app-summary-id-mismatch"
    if root.get("user") is not False:
        return None, "native-app-summary-built-in-unverified"
    if root.get("parentId") not in (None, "") or root.get("parentAppId") not in (None, ""):
        return None, "native-app-summary-parent-conflict"
    if root.get("type") not in (None, "Rule Machine"):
        return None, "native-app-summary-type-conflict"
    reported_class_id = _id(root.get("appTypeId"))
    if (reported_class_id is not None and candidate_type_id is not None
            and reported_class_id != candidate_type_id):
        return None, "native-app-summary-class-id-conflict"
    # MCP 5.1.5 adds the source-observed namespace directly to the thin
    # summary=true response. It deliberately does not render an app page or
    # promise the full app.appType object. Older full/extended records may
    # carry that nested object instead. Never invent namespace from the label.
    flat_namespace = root.get("namespace")
    typed = root.get("appType")
    if typed is None:
        if flat_namespace is None:
            return None, "native-app-summary-class-namespace-unavailable"
        # Without a nested type, both identity fields must be attested by
        # the same thin app summary, not inferred from the instance listing.
        if flat_namespace != "hubitat" or root.get("type") != "Rule Machine":
            return None, "native-app-summary-class-namespace-unverified"
        type_id = None
    else:
        # A malformed or contradictory full type must not be silently
        # disregarded just because the flat namespace looks correct.
        if not isinstance(typed, dict):
            return None, "native-app-summary-class-namespace-unavailable"
        if typed.get("namespace") != "hubitat" or typed.get("name") != "Rule Machine":
            return None, "native-app-summary-class-namespace-unverified"
        if flat_namespace is not None and flat_namespace != typed.get("namespace"):
            return None, "native-app-summary-class-namespace-unverified"
        if typed.get("system") is False or typed.get("isBuiltIn") is False:
            return None, "native-app-summary-system-conflict"
        type_id = _id(typed.get("id"))
    if type_id is not None and candidate_type_id is not None and type_id != candidate_type_id:
        return None, "native-app-summary-class-id-conflict"
    return {
        "appId": candidate_id,
        "appTypeId": candidate_type_id or type_id,
        "namespace": "hubitat",
        "name": "Rule Machine",
        "proof": "source-typed-installed-app-summary",
    }, ""


def _native_catalog_row_conflicts(row: dict[str, Any]) -> bool:
    """A missing namespace is not a contradictory namespace.

    The MCP type listing combines userAppTypes with built-in systemAppTypes.
    The latter can have system/isBuiltIn=true while omitting namespace.
    A separate installed-app summary can authoritatively supply that field.
    Explicit contrary class name/namespace or user-code flags still veto.
    """
    namespace = row.get("namespace")
    return (
        row.get("name") != "Rule Machine"
        or namespace not in (None, "", "hubitat")
        or row.get("system") is False
        or row.get("isBuiltIn") is False
    )


def _safe_catalog_conflict(row: dict[str, Any], type_id: str) -> dict[str, Any]:
    """Publish only the relevant identity conflict, never third-party names."""
    namespace = row.get("namespace")
    return {
        "appTypeId": type_id,
        "classNameMatches": row.get("name") == "Rule Machine",
        "namespaceEvidence": (
            "absent" if namespace in (None, "") else
            "hubitat" if namespace == "hubitat" else "conflicting"
        ),
        "system": row.get("system") if type(row.get("system")) is bool else None,
        "isBuiltIn": (
            row.get("isBuiltIn")
            if type(row.get("isBuiltIn")) is bool else None
        ),
    }


def project_rule_inventory(instances: Any, types: Any, rules: Any, summaries: dict[str, Any] | None = None) -> dict[str, Any]:
    inst, inst_complete = _collection(instances, "apps", total_field="totalOnHub")
    type_rows, types_complete = _collection(types, "apps")
    rule_rows, rules_complete = _collection(rules, "rules")
    # The upstream type endpoint can be count-complete for *community*
    # classes while its separate built-in type enrichment is missing.
    note = types.get("note") if isinstance(types, dict) else None
    if isinstance(note, str) and (
        "built-in" in note.lower()
        and any(w in note.lower() for w in (
            "omitted", "unavailable", "unexpected", "could not",
        ))
    ):
        types_complete = False
    summaries = summaries if isinstance(summaries, dict) else {}
    native_types = {
        _id(row.get("id")) for row in type_rows
        if row.get("namespace") == "hubitat"
        and row.get("name") == "Rule Machine"
        and row.get("system") is not False
        and row.get("isBuiltIn") is not False
        and _id(row.get("id"))
    }
    parents = []
    possible = []
    summaries_checked = []
    catalog_class_conflicts: list[dict[str, Any]] = []
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
            # A separate, read-only identity record may expose the exact
            # native appType namespace/name when the catalog omits it.
            if app_id in summaries:
                candidate, gap = _native_parent_from_summary(
                    summaries[app_id], candidate_id=app_id,
                    candidate_type_id=app_type,
                )
                summaries_checked.append({
                    "appId": app_id, "typeProofGap": gap or None,
                })
                if candidate is not None:
                    # An explicit contradictory class with the same native
                    # type ID outranks a summary claim. Missing catalog
                    # rows are a gap; disagreeing rows are a conflict.
                    contradictions = [
                        t for t in type_rows
                        if app_type is not None
                        and _id(t.get("id")) == app_type
                        and _native_catalog_row_conflicts(t)
                    ]
                    if not contradictions:
                        parents.append(candidate)
                        continue
                    # Only a genuine contradiction vetoes the independent
                    # thin installed-app summary. A built-in catalog class
                    # with a missing namespace is *not* one.
                    catalog_class_conflicts.extend(
                        _safe_catalog_conflict(t, app_type)
                        for t in contradictions[:6]
                    )
                    summaries_checked[-1]["typeProofGap"] = (
                        "native-app-summary-catalog-conflict"
                    )
            # Upstream installed-app rows can legitimately omit appTypeId.
            # Preserve the *specific* missing join rather than implying
            # namespace "hubitat" from a label or child count.
            possible.append({
                "appId": app_id,
                "appTypeId": app_type,
                "typeProof": "unverified",
                "typeProofGap": (
                    "instance-appTypeId-absent" if app_type is None
                    else "no-matching-native-app-type-id"
                ),
            })

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
        "summarySourceChecks": summaries_checked[:20],
        "catalogClassConflicts": catalog_class_conflicts[:6],
        # Retain only the bounded built-in Rule Machine type-class IDs
        # needed to diagnose the join; never publish unrelated app names,
        # installed app inventories or private source code.
        "nativeRuleMachineTypeIds": sorted(
            (t for t in native_types if t is not None),
            key=lambda item: int(item),
        )[:20],
        # A count-complete app-type page can still lack the native class
        # needed to resolve an installed candidate. Do not present that
        # unresolved instance/type join as a complete parent identity.
        # A successful independent typed summary can prove the parent even
        # when the built-in type catalog remains incomplete.
        "parentIdentityComplete": (
            inst_complete and not possible and (types_complete or bool(parents))
        ),
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
            + ", ".join(
                "ID **" + p["appId"] + "** "
                + "(type **" + p["name"] + "**, namespace **"
                + p["namespace"] + "**)"
                for p in parents
            ) + "."
        )
    elif data["candidateParents"]:
        ids = ", ".join(x["appId"] for x in data["candidateParents"])
        gaps = sorted({
            item.get("typeProofGap", "unknown-native-type-link")
            for item in data["candidateParents"]
        })
        lines.append(
            "Rule Machine-named app instance ID(s) "
            + ids + " were returned, but their built-in app-type identity "
            "could not be linked to those instance IDs. The native parent "
            "ID remains unresolved."
        )
        if gaps == ["instance-appTypeId-absent"]:
            lines.append(
                "The instance listing did not provide an appTypeId for "
                "the Rule Machine candidate; matching the name alone "
                "would not prove the native type."
            )
        elif gaps == ["no-matching-native-app-type-id"]:
            lines.append(
                "The candidate's appTypeId did not match a typed native "
                "Rule Machine class in the returned app-type listing."
            )
        for check in data.get("summarySourceChecks", []):
            if check.get("appId") in {p["appId"] for p in data["candidateParents"]}:
                reason = check.get("typeProofGap")
                if reason == "native-app-summary-class-namespace-unavailable":
                    lines.append(
                        "The independent app summary omitted its native "
                        "appType namespace/name. A built-in name alone "
                        "cannot establish the native writer parent."
                    )
                elif reason == "native-app-summary-catalog-conflict":
                    lines.append(
                        "The exact class-ID catalog record contradicts the "
                        "installed app's independent native summary. "
                        "Identity remains unverified; the Technical details "
                        "include redacted class-identity conflict fields."
                    )
                elif reason and reason != "native-app-summary-unavailable":
                    lines.append(
                        "Independent app-summary verification remains "
                        "unresolved (" + reason.replace("-", " ") + ")."
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
    # Only for an unverified parent: one exact-ID, read-only thin summary.
    # This endpoint does not render the form or modify the hub.
    if (not projection["parents"] and projection["candidateParents"]
            and "hub_read_apps_code" in available_names):
        candidate_id = projection["candidateParents"][0]["appId"]
        summary = await get(
            "hub_read_apps_code", "hub_get_app_config",
            {"appId": candidate_id, "summary": True},
        )
        projection = project_rule_inventory(
            inst, types, rules, summaries={candidate_id: summary},
        )
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
