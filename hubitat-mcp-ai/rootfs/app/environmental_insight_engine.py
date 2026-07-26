from typing import Any


def build_environmental_insights(
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:

    insights = []

    temperatures = evidence.get("temperatures", [])
    humidities = evidence.get("humidities", [])

    if temperatures:
        hottest = max(
            temperatures,
            key=lambda x: float(x.get("value") or 0)
        )

        if float(hottest.get("value") or 0) >= 28:
            insights.append(
                {
                    "type": "thermal",
                    "room": hottest.get("room"),
                    "finding": "Room temperature is elevated",
                    "evidence": [
                        f'{hottest.get("device")}: {hottest.get("value")} C'
                    ],
                }
            )

    if humidities:
        highest = max(
            humidities,
            key=lambda x: float(x.get("value") or 0)
        )

        if float(highest.get("value") or 0) >= 50:
            insights.append(
                {
                    "type": "humidity",
                    "room": highest.get("room"),
                    "finding": "Humidity is elevated",
                    "evidence": [
                        f'{highest.get("device")}: {highest.get("value")}%'
                    ],
                }
            )

    return insights


__all__ = [
    "build_environmental_insights",
]
