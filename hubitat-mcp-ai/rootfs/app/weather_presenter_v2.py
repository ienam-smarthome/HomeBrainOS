from __future__ import annotations

from typing import Any

from presenter import compact_number, display_payload, first_value, normalise_text, walk


WEATHER_KEYS = {
    "weathersummary",
    "weathersummaryline",
    "summary",
    "todaysummary",
    "forecasttext",
    "condition",
    "currentcondition",
    "weathercondition",
    "weather",
    "temperature",
    "currenttemperature",
    "humidity",
    "precipitation",
    "precipitationnow",
    "rain",
    "rainfall",
    "raintoday",
    "rainchance",
    "precipprobability",
}


def _attribute_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, list):
        return {}

    result: dict[str, Any] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("attribute") or item.get("key")
        if not name:
            continue
        current = item.get("currentValue")
        if current in (None, ""):
            current = item.get("value")
        if current in (None, ""):
            current = item.get("currentState")
        result[str(name)] = current
    return result


def _combined_candidate(item: dict[str, Any]) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    for key in ("attributes", "currentStates", "states", "state"):
        combined.update(_attribute_map(item.get(key)))
    combined.update(item)
    return combined


def _weather_score(item: dict[str, Any]) -> int:
    combined = _combined_candidate(item)
    lowered_keys = {str(key).lower() for key in combined}
    text = " ".join(
        str(item.get(key) or "")
        for key in ("label", "name", "displayName", "type", "deviceType")
    ).lower()
    score = len(lowered_keys & WEATHER_KEYS) * 5
    if "weather" in text:
        score += 20
    if "forecast" in text:
        score += 8
    return score


def _pick_weather(value: Any) -> dict[str, Any]:
    candidates = [item for item in walk(value) if isinstance(item, dict)]
    if not candidates:
        return {}
    ranked = sorted(candidates, key=_weather_score, reverse=True)
    return _combined_candidate(ranked[0])


def _value(data: dict[str, Any], *names: str) -> Any:
    value = first_value(data, *names)
    if isinstance(value, dict):
        for key in ("currentValue", "value", "text", "summary"):
            nested = value.get(key)
            if nested not in (None, ""):
                return nested
    return value


def present_weather(value: Any) -> tuple[str, dict[str, Any]]:
    weather = _pick_weather(value)

    summary = _value(
        weather,
        "weatherSummary",
        "weatherSummaryLine",
        "summary",
        "todaySummary",
        "forecastText",
    )
    condition = _value(
        weather,
        "condition",
        "currentCondition",
        "weatherCondition",
        "weather",
    )
    temperature = compact_number(
        _value(weather, "temperature", "currentTemperature", "temp"),
        "°C",
    )
    humidity = compact_number(_value(weather, "humidity", "relativeHumidity"), "%")
    precipitation = _value(
        weather,
        "precipitation",
        "precipitationNow",
        "rain",
        "rainfall",
        "rainToday",
    )
    rain_chance = compact_number(
        _value(
            weather,
            "rainChance",
            "chanceOfRain",
            "precipProbability",
            "precipitationProbability",
        ),
        "%",
    )

    clean_summary = normalise_text(summary) if summary not in (None, "") else ""
    clean_condition = normalise_text(condition) if condition not in (None, "") else None
    clean_precipitation = (
        normalise_text(precipitation)
        if precipitation not in (None, "")
        else None
    )

    details = [
        detail
        for detail in (
            clean_condition,
            temperature,
            humidity,
            f"rain chance {rain_chance}" if rain_chance else None,
            f"rainfall {clean_precipitation}" if clean_precipitation else None,
        )
        if detail
    ]

    if clean_summary:
        message = clean_summary
        if details and not any(str(detail).lower() in clean_summary.lower() for detail in details):
            message += "\n" + " · ".join(details) + "."
    elif details:
        message = "Weather: " + " · ".join(details) + "."
    else:
        message = (
            "A weather device was found, but it did not expose a readable summary, "
            "condition, temperature, humidity, or rain value."
        )

    metrics: list[dict[str, Any]] = []
    for label, metric_value, icon in (
        ("Condition", clean_condition, "🌦️"),
        ("Temperature", temperature, "🌡️"),
        ("Humidity", humidity, "💧"),
        ("Rain chance", rain_chance, "☔"),
        ("Rainfall", clean_precipitation, "🌧️"),
    ):
        if metric_value not in (None, ""):
            metrics.append(
                {
                    "label": label,
                    "value": str(metric_value),
                    "icon": icon,
                }
            )

    subtitle = clean_summary or (
        " · ".join(details[:3]) if details else "Weather data incomplete"
    )
    return (
        message,
        display_payload(
            "weather",
            "Weather",
            subtitle=subtitle,
            metrics=metrics,
            note=(
                "Open Technical details to inspect the weather device attributes."
                if not metrics
                else None
            ),
        ),
    )
