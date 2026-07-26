from typing import Any


def build_thermal_insight(devices: list[dict[str, Any]], room: str):
    room_key = room.lower().replace(" ", "")

    temperatures = []
    trvs = []
    contacts = []

    for device in devices:
        label = str(
            device.get("label")
            or device.get("name")
            or ""
        )

        name = label.lower().replace(" ", "")

        if room_key not in name:
            continue

        states = device.get("attributes") or device.get("currentStates") or {}

        if "temperature" in str(states).lower():
            temperatures.append({
                "device": label,
                "temperature": states.get("temperature")
            })

        if "thermostat" in str(device).lower() or "valve" in str(device).lower():
            trvs.append(label)

        if "contact" in str(device).lower():
            contacts.append({
                "device": label,
                "state": states.get("contact")
            })

    return {
        "room": room,
        "temperatures": temperatures,
        "trvs": trvs,
        "contacts": contacts,
        "diagnosis_ready": bool(temperatures),
    }


__all__ = [
    "build_thermal_insight",
]
