from typing import Any


def build_humidity_insight(
    devices: list[dict[str, Any]],
    room: str,
):
    room_key = room.lower().replace(" ", "")

    humidity = []
    fans = []
    motion = []

    for device in devices:
        label = str(
            device.get("label")
            or device.get("name")
            or ""
        )

        name = label.lower().replace(" ", "")

        if room_key not in name:
            continue

        states = (
            device.get("attributes")
            or device.get("currentStates")
            or {}
        )

        if "humidity" in str(states).lower():
            humidity.append(
                {
                    "device": label,
                    "humidity": states.get("humidity"),
                }
            )

        capabilities = str(
            device.get("capabilities")
            or ""
        ).lower()

        if "fan" in capabilities or "switch" in capabilities:
            fans.append(label)

        if "motion" in capabilities:
            motion.append(label)

    return {
        "room": room,
        "humidity": humidity,
        "fans": fans,
        "motion": motion,
        "diagnosis_ready": bool(humidity),
    }


__all__ = [
    "build_humidity_insight",
]
