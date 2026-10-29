"""Source-verified room membership and natural-language multi-device answers.

A model chooses which READ operations to request. Only an identity-matched
Hubitat room response may authorise room member IDs. Device states require
separate, same-ID successful hub_get_device receipts. No keyword routing,
implicit device writes, or fabricated membership.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .native_source_adapters import safe_string, unwrapped
from .native_entity_group_answer import _attributes, _id, entity_group_answer


def _normal(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def verified_room_inventory(source: Any, requested: Any, *,
                            read: int) -> dict[str, Any] | None:
    """Admit member IDs only from an actual returned, same-named room."""
    if not isinstance(requested, str) or not requested.strip():
        return None
    data = unwrapped(source)
    if not isinstance(data, Mapping):
        return None
    if isinstance(data.get("room"), Mapping):
        data = data["room"]
    name = data.get("name")
    if not isinstance(name, str) or _normal(name) != _normal(requested):
        return None
    members = data.get("devices")
    if not isinstance(members, list) or len(members) > 60:
        return None
    found: dict[str, str] = {}
    for item in members:
        if not isinstance(item, Mapping):
            return None
        ident = _id(item.get("id") if item.get("id") is not None
                    else item.get("deviceId"))
        if not ident or ident in found:
            return None
        label = item.get("label") or item.get("name")
        found[ident] = safe_string(label, 90) if isinstance(label, str) else ""
    count = data.get("deviceCount")
    # Missing or inconsistent counts do not prove complete room coverage.
    complete = type(count) is int and count == len(members)
    return {
        "name": safe_string(name, 90), "read": read,
        "member_ids": list(found), "members": found,
        "reported_count": count if type(count) is int and count >= 0 else None,
        "inventory_complete": complete, "authority": "verified_hub_get_room",
    }


def _joined_device(witnesses: Sequence[Mapping[str, Any]],
                   ident: str) -> dict[str, Any] | None:
    for w in witnesses:
        if not isinstance(w, Mapping) or w.get("operation") != "hub_get_device":
            continue
        args, source = w.get("read_filters"), w.get("source_data")
        if not isinstance(args, Mapping) or not isinstance(source, Mapping):
            continue
        if (_id(args.get("deviceId")) != ident
                or _id(source.get("id")) != ident
                or type(w.get("read")) is not int):
            continue
        label = source.get("label") or source.get("name")
        if not isinstance(label, str) or not label.strip():
            continue
        capabilities = source.get("capabilities")
        caps = set(capabilities[:80]) if isinstance(capabilities, list) else set()
        return {
            "id": ident, "label": safe_string(label, 90),
            "light": "Light" in caps,
            "values": _attributes(source), "read": w["read"],
        }
    return None


def _human_state(item: Mapping[str, Any]) -> str:
    values = item["values"]
    phrases = []
    if "switch" in values:
        phrases.append("on" if values["switch"] == "on" else "off")
    elif "motion" in values:
        phrases.append("motion is " + values["motion"])
    elif "presence" in values:
        phrases.append("presence is " + values["presence"])
    elif "contact" in values:
        phrases.append("contact is " + values["contact"])
    for key, title in (("temperature", "temperature"), ("humidity", "humidity"),
                       ("battery", "battery"), ("power", "power")):
        if key in values:
            phrases.append(f"{title} {values[key]}")
    if not phrases:
        for key in ("healthStatus", "networkStatus"):
            if key in values:
                phrases.append("reported " + values[key])
                break
    if not phrases:
        return "no recognised current state was returned"
    detail = ", ".join(phrases[:3])
    if item["light"] and "level" in values:
        detail += (f"; saved dimmer level {values['level']}"
                   " (not proof the light is illuminated)")
    return detail


def natural_entity_answer(
    lookups: Sequence[Mapping[str, Any]],
    witnesses: Sequence[Mapping[str, Any]],
    rooms: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any] | None:
    """Compose a human answer from proof-joined device and room evidence."""
    groups = [x for x in lookups if isinstance(x, Mapping)
              and x.get("status") == "candidate_group"]
    base = entity_group_answer(lookups, witnesses) if groups else None
    if groups and base is None:
        # An incomplete requested group must never look fully verified.
        return None
    requested = (safe_string(groups[-1].get("query"), 90) if groups
                 else safe_string(rooms[-1].get("name"), 90)
                 if rooms else "")
    if not requested:
        return None
    room = next((r for r in reversed(rooms)
                 if isinstance(r, Mapping)
                 and _normal(r.get("name")) == _normal(requested)
                 and r.get("authority") == "verified_hub_get_room"), None)
    name_ids = ([_id(x) for x in groups[-1].get("candidate_ids", [])]
                if groups else [])
    if not name_ids and room is None:
        return None
    room_ids = list(room["member_ids"]) if room else []
    ids = list(dict.fromkeys(name_ids + room_ids))[:60]
    checked = {ident: device for ident in ids
               if (device := _joined_device(witnesses, ident)) is not None}
    if not checked:
        return None
    if not name_ids and room is not None and not (set(room_ids) & set(checked)):
        return None
    if name_ids and not set(name_ids).issubset(checked):
        return None

    # Name matching and membership are separate relationships.
    name_lights = [checked[i] for i in name_ids if checked[i]["light"]]
    room_lights = [checked[i] for i in room_ids
                   if i in checked and checked[i]["light"]]
    room_only = [i for i in room_ids if i not in name_ids]
    unread_room = [i for i in room_ids if i not in checked]
    lines = []
    main = name_lights or room_lights
    if main:
        on = [x["label"] for x in main if x["values"].get("switch") == "on"]
        off = [x["label"] for x in main if x["values"].get("switch") == "off"]
        unknown = [x["label"] for x in main
                   if x["values"].get("switch") not in ("on", "off")]
        if len(main) == 2 and len(off) == 2:
            lines.append(f"**{off[0]} and {off[1]} are both off**, according to Hubitat.")
        elif len(main) == 2 and len(on) == 2:
            lines.append(f"**{on[0]} and {on[1]} are both on**, according to Hubitat.")
        else:
            bits = []
            if on:
                bits.append("on: " + ", ".join(on))
            if off:
                bits.append("off: " + ", ".join(off))
            if unknown:
                bits.append("not confirmed: " + ", ".join(unknown))
            lines.append("**Hubitat light status:** " + "; ".join(bits) + ".")
    else:
        lines.append(f"**{requested}:** I verified {len(checked)} device reading(s), "
                     "but none of the checked devices advertised the Light capability.")

    # All requested name-matched devices are included; additional verified
    # room members are shown separately without pretending name match.
    listed = [checked[i] for i in name_ids if i in checked] if name_ids else [
        checked[i] for i in room_ids if i in checked]
    if listed:
        lines.append("")
        for item in listed:
            lines.append(f"- **{item['label']}:** {_human_state(item)}.")
    if room:
        lines.extend(["", f"**Actual {room['name']} room membership:** "
                      + (f"Hubitat lists {len(room_ids)} devices."
                         if room["inventory_complete"] else
                         "Hubitat returned a partial or unconfirmed member list.")])
        extras = [checked[i] for i in room_only if i in checked]
        if extras:
            lines.append("Other devices in this room (regardless of their names):")
            for item in extras:
                lines.append(f"- **{item['label']}:** {_human_state(item)}.")
        if unread_room:
            names = [room["members"].get(i) or f"device {i}"
                     for i in unread_room[:10]]
            lines.append("**Not yet checked:** " + ", ".join(names)
                         + " — room membership was reported, but current "
                           "device state was not independently read.")
        if name_ids and room["inventory_complete"]:
            outside = [checked[i]["label"] for i in name_ids if i not in room_ids]
            if outside:
                lines.append("These name-matched devices are **not listed in "
                             f"the {room['name']} room**: " + ", ".join(outside)
                             + ". Their assignment to another room was not checked.")
    else:
        lines.append("")
        lines.append("**Room membership is not verified.** These devices matched "
                     "by name; a separate room read is needed to find members "
                     "with different names.")

    lines.append("")
    lines.append("*These are Hubitat's reported readings, not independent "
                 "physical confirmation. A saved brightness level does not "
                 "mean an off light is illuminated.*")
    evidence = sorted({item["read"] for item in checked.values()}
                      | ({room["read"]} if room else set()))
    return {
        "text": "\n".join(lines),
        "candidate_count": len(name_ids) if name_ids else len(room_ids),
        "verified_device_read_count": len(checked),
        "matched_light_count": len(name_lights) if name_ids else len(room_lights),
        "room_membership_verified": bool(room and room["inventory_complete"]),
        "room_inventory_complete": room["inventory_complete"] if room else True,
        "room_unread_count": len(unread_room),
        "room_only_count": len(room_only),
        "evidence_reads": evidence,
        "authority": "identity_and_same_id_device_and_optional_room_receipts",
    }


__all__ = ["verified_room_inventory", "natural_entity_answer"]
