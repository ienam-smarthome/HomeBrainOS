from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
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
    "precipitationtoday",
    "rain",
    "rainfall",
    "raintoday",
    "rainchance",
    "precipprobability",
    "threedayfcsttile",
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
    if "weather" in text or "open-meteo" in text:
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


def _normalise_query(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _weather_period(query: str) -> str:
    q = _normalise_query(query)
    if any(term in q for term in ("tomorrow", "next day")):
        return "tomorrow"
    if any(
        term in q
        for term in (
            "right now",
            "currently",
            "current weather",
            "weather now",
            "raining now",
            "rain now",
        )
    ) or q.endswith(" now"):
        return "now"
    if "today" in q:
        return "today"
    return "overview"


def _rain_question(query: str) -> bool:
    q = _normalise_query(query)
    return any(
        term in q
        for term in ("rain", "raining", "umbrella", "precipitation", "wet weather")
    )


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _summary_values(weather: dict[str, Any]) -> dict[str, Any]:
    summary = normalise_text(
        _value(
            weather,
            "weatherSummary",
            "weatherSummaryLine",
            "summary",
            "todaySummary",
            "forecastText",
        )
        or ""
    )

    def find(pattern: str) -> str | None:
        match = re.search(pattern, summary, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    return {
        "summary": summary,
        "condition": find(
            r"(?:updated at \d{1,2}:\d{2}[.,]?\s*)?([A-Za-z][A-Za-z ]+?)\s+with a high"
        ),
        "high": find(r"high of?\s*(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C"),
        "low": find(r"low of?\s*(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C"),
        "current": find(
            r"current temperature is\s*(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C"
        ),
        "feels": find(r"feels like\s*(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C"),
        "precip_now": find(
            r"precipitation now is\s*(.+?)(?=\.\s*(?:chance|$)|$)"
        ),
        "chance": find(
            r"chance of precipitation is\s*(\d+(?:\.\d+)?)\s*%"
        ),
    }


def _forecast_tokens(raw: Any) -> list[str]:
    source = html_lib.unescape(str(raw or ""))
    if not source:
        return []
    source = (
        source.replace("\\u003c", "<")
        .replace("\\u003e", ">")
        .replace("\\n", "\n")
        .replace("\\t", " ")
    )

    class VisibleTextParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.tokens: list[str] = []
            self.ignore_depth = 0

        def handle_starttag(
            self,
            tag: str,
            attrs: list[tuple[str, str | None]],
        ) -> None:
            if tag.lower() in {"script", "style"}:
                self.ignore_depth += 1

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() in {"script", "style"} and self.ignore_depth:
                self.ignore_depth -= 1

        def handle_data(self, data: str) -> None:
            if self.ignore_depth:
                return
            value = normalise_text(data)
            if value:
                self.tokens.extend(
                    part.strip() for part in value.splitlines() if part.strip()
                )

    parser = VisibleTextParser()
    try:
        parser.feed(source)
        parser.close()
        return parser.tokens
    except Exception:
        return [
            part.strip()
            for part in re.split(r"[|\n]+", normalise_text(source))
            if part.strip()
        ]


def _tomorrow_forecast(weather: dict[str, Any]) -> dict[str, Any]:
    tokens = _forecast_tokens(
        _value(
            weather,
            "threedayfcstTile",
            "threeDayForecastTile",
            "threeDayForecast",
            "forecastTile",
        )
    )
    tomorrow_weekday = (datetime.now() + timedelta(days=1)).strftime("%a").lower()

    day_aliases = {
        "tod": "today",
        "today": "today",
        "tom": "tomorrow",
        "tomorrow": "tomorrow",
        "mon": "mon",
        "monday": "mon",
        "tue": "tue",
        "tues": "tue",
        "tuesday": "tue",
        "wed": "wed",
        "wednesday": "wed",
        "thu": "thu",
        "thur": "thu",
        "thurs": "thu",
        "thursday": "thu",
        "fri": "fri",
        "friday": "fri",
        "sat": "sat",
        "saturday": "sat",
        "sun": "sun",
        "sunday": "sun",
    }

    def day_key(token: str) -> str | None:
        return day_aliases.get(_normalise_query(token))

    def condition_value(token: str) -> str | None:
        match = re.fullmatch(
            r"(Sunny|Clear|Mostly sunny|Partly cloudy|Mostly cloudy|Cloudy|"
            r"Overcast|Light rain|Rain|Heavy rain|Showers|Light showers|"
            r"Drizzle|Thunderstorms?|Snow|Sleet|Fog|Mist)",
            re.sub(r"\s+", " ", token).strip(),
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else None

    def high_low_value(token: str) -> tuple[str, str] | None:
        match = re.search(
            r"(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C\s*/\s*"
            r"(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C",
            token,
            flags=re.IGNORECASE,
        )
        return (match.group(1), match.group(2)) if match else None

    result: dict[str, Any] = {
        "available": False,
        "condition": None,
        "high": None,
        "low": None,
        "chance": None,
        "amount": None,
        "tokens": tokens,
    }
    headers = [
        (index, key)
        for index, token in enumerate(tokens)
        for key in [day_key(token)]
        if key
    ]
    if not headers:
        return result

    tomorrow_column = next(
        (column for column, (_index, key) in enumerate(headers) if key == "tomorrow"),
        None,
    )
    if tomorrow_column is None:
        tomorrow_column = next(
            (
                column
                for column, (_index, key) in enumerate(headers)
                if key == tomorrow_weekday
            ),
            None,
        )
    if tomorrow_column is None:
        return result

    day_count = len(headers)
    tail = tokens[headers[-1][0] + 1 :]
    conditions = [
        condition
        for token in tail
        for condition in [condition_value(token)]
        if condition
    ]
    high_lows = [
        pair
        for token in tail
        for pair in [high_low_value(token)]
        if pair
    ]
    chances: list[str] = []
    amounts: list[str] = []
    for token in tail:
        chance = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", token)
        if chance:
            chances.append(chance.group(1))
        amount = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*mm\s*",
            token,
            flags=re.IGNORECASE,
        )
        if amount:
            amounts.append(amount.group(1))

    if len(conditions) >= day_count:
        result["condition"] = conditions[tomorrow_column]
    if len(high_lows) >= day_count:
        result["high"], result["low"] = high_lows[tomorrow_column]
    if len(chances) >= day_count:
        result["chance"] = chances[tomorrow_column]
    if len(amounts) >= day_count:
        result["amount"] = amounts[tomorrow_column]

    if not any(
        result.get(key) for key in ("condition", "high", "low", "chance", "amount")
    ):
        start = headers[tomorrow_column][0] + 1
        end = (
            headers[tomorrow_column + 1][0]
            if tomorrow_column + 1 < day_count
            else len(tokens)
        )
        segment = tokens[start:end]
        for token in segment:
            if result["condition"] is None:
                result["condition"] = condition_value(token)
            if result["high"] is None:
                pair = high_low_value(token)
                if pair:
                    result["high"], result["low"] = pair
            if result["chance"] is None:
                chance = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", token)
                if chance:
                    result["chance"] = chance.group(1)
            if result["amount"] is None:
                amount = re.fullmatch(
                    r"\s*(\d+(?:\.\d+)?)\s*mm\s*",
                    token,
                    flags=re.IGNORECASE,
                )
                if amount:
                    result["amount"] = amount.group(1)

    result["available"] = any(
        result.get(key) not in (None, "")
        for key in ("condition", "high", "low", "chance", "amount")
    )
    return result


def _rain_answer(
    label: str,
    chance: Any,
    amount: Any,
    current: str | None = None,
) -> tuple[str, str]:
    chance_number = _safe_float(chance)
    amount_number = _safe_float(amount)
    if amount_number is None and current:
        amount_match = re.search(r"(\d+(?:\.\d+)?)\s*mm", current, flags=re.IGNORECASE)
        if amount_match:
            amount_number = float(amount_match.group(1))

    if chance_number is None and amount_number is None:
        statement = f"Rain information for {label.lower()} is not available."
        return f"{label}: {statement}", statement

    likely = (
        (amount_number is not None and amount_number > 0)
        or (chance_number is not None and chance_number >= 50)
    )
    possible = not likely and chance_number is not None and chance_number > 0
    if likely:
        statement = "Rain is likely."
    elif possible:
        statement = "Rain is possible."
    else:
        statement = "No rain is expected."

    message = f"{label}: {statement}"
    details: list[str] = []
    if chance_number is not None:
        details.append(f"rain chance {chance_number:g}%")
    if amount_number is not None:
        details.append(
            f"forecast rain {amount_number:g} mm"
            if label.lower() == "tomorrow"
            else f"rainfall {amount_number:g} mm"
        )
    if details:
        message += " " + "; ".join(details) + "."
    if current:
        message += f" It is currently {current}."
    return message, statement


def _metric(label: str, value: Any, icon: str) -> dict[str, str] | None:
    if value in (None, ""):
        return None
    return {"label": label, "value": str(value), "icon": icon}


def present_weather(
    value: Any,
    query: str = "weather",
) -> tuple[str, dict[str, Any]]:
    weather = _pick_weather(value)
    values = _summary_values(weather)
    tomorrow = _tomorrow_forecast(weather)
    period = _weather_period(query)
    rain_only = _rain_question(query)
    if rain_only and period == "overview":
        period = "today"

    condition = values.get("condition") or _value(
        weather,
        "condition",
        "currentCondition",
        "weatherCondition",
        "weather",
    )
    condition = normalise_text(condition) if condition not in (None, "") else None
    current_temp = values.get("current") or compact_number(
        _value(weather, "temperature", "currentTemperature", "temp")
    )
    humidity = compact_number(_value(weather, "humidity", "relativeHumidity"), "%")
    precip_now = values.get("precip_now") or _value(
        weather,
        "precipitationNow",
        "precipitation",
        "rainToday",
        "rainfall",
        "rain",
    )
    precip_now = normalise_text(precip_now) if precip_now not in (None, "") else None
    today_chance = values.get("chance") or compact_number(
        _value(
            weather,
            "rainChance",
            "chanceOfRain",
            "precipProbability",
            "precipitationProbability",
        )
    )

    metrics: list[dict[str, str]] = []
    note: str | None = None

    if period == "tomorrow":
        if rain_only:
            message, statement = _rain_answer(
                "Tomorrow",
                tomorrow.get("chance"),
                tomorrow.get("amount"),
            )
            extras: list[str] = []
            if tomorrow.get("condition"):
                extras.append(f"conditions {tomorrow['condition']}")
            if tomorrow.get("high") and tomorrow.get("low"):
                extras.append(
                    f"high {tomorrow['high']}°C, low {tomorrow['low']}°C"
                )
            if extras:
                message += " " + "; ".join(extras) + "."
            title = "Rain tomorrow"
            subtitle = statement
        else:
            parts: list[str] = []
            if tomorrow.get("condition"):
                parts.append(str(tomorrow["condition"]))
            if tomorrow.get("high") and tomorrow.get("low"):
                parts.append(
                    f"high {tomorrow['high']}°C, low {tomorrow['low']}°C"
                )
            if tomorrow.get("chance") is not None:
                parts.append(f"rain chance {tomorrow['chance']}%")
            if tomorrow.get("amount") is not None:
                parts.append(f"forecast rain {tomorrow['amount']} mm")
            message = (
                "Tomorrow: " + ". ".join(parts).rstrip(".") + "."
                if parts
                else "Tomorrow's forecast is not available from the weather device."
            )
            title = "Weather tomorrow"
            subtitle = " · ".join(parts) if parts else "Forecast unavailable"

        for item in (
            _metric("Condition", tomorrow.get("condition"), "🌦️"),
            _metric(
                "High",
                f"{tomorrow['high']}°C" if tomorrow.get("high") else None,
                "🔺",
            ),
            _metric(
                "Low",
                f"{tomorrow['low']}°C" if tomorrow.get("low") else None,
                "🔻",
            ),
            _metric(
                "Rain chance",
                f"{tomorrow['chance']}%" if tomorrow.get("chance") is not None else None,
                "☔",
            ),
            _metric(
                "Forecast rain",
                f"{tomorrow['amount']} mm" if tomorrow.get("amount") is not None else None,
                "🌧️",
            ),
        ):
            if item:
                metrics.append(item)
        if not tomorrow.get("available"):
            note = "The weather device did not expose a readable tomorrow forecast."

    elif period == "today":
        if rain_only:
            message, statement = _rain_answer(
                "Today",
                today_chance,
                None,
                precip_now,
            )
            title = "Rain today"
            subtitle = statement
            for item in (
                _metric(
                    "Rain chance",
                    f"{_safe_float(today_chance):g}%"
                    if _safe_float(today_chance) is not None
                    else None,
                    "☔",
                ),
                _metric("Rain now", precip_now, "🌧️"),
            ):
                if item:
                    metrics.append(item)
        else:
            parts: list[str] = []
            if condition:
                parts.append(condition.rstrip(".,"))
            if values.get("high") and values.get("low"):
                parts.append(f"high {values['high']}°C, low {values['low']}°C")
            if today_chance is not None:
                chance_number = _safe_float(today_chance)
                parts.append(
                    f"rain chance {chance_number:g}%"
                    if chance_number is not None
                    else f"rain chance {today_chance}"
                )
            if precip_now:
                parts.append(f"currently {precip_now}")
            message = (
                "Today: " + ". ".join(parts).rstrip(".") + "."
                if parts
                else values.get("summary")
                or "Today's weather is not available from the weather device."
            )
            title = "Weather today"
            subtitle = " · ".join(parts) if parts else "Weather data incomplete"
            for item in (
                _metric("Condition", condition, "🌦️"),
                _metric("Current", f"{current_temp}°C" if current_temp else None, "🌡️"),
                _metric(
                    "High",
                    f"{values['high']}°C" if values.get("high") else None,
                    "🔺",
                ),
                _metric(
                    "Low",
                    f"{values['low']}°C" if values.get("low") else None,
                    "🔻",
                ),
                _metric("Humidity", humidity, "💧"),
            ):
                if item:
                    metrics.append(item)

    elif period == "now":
        if rain_only:
            message, statement = _rain_answer(
                "Now",
                today_chance,
                None,
                precip_now,
            )
            title = "Rain now"
            subtitle = statement
        else:
            parts: list[str] = []
            if condition:
                parts.append(condition.rstrip(".,"))
            if current_temp:
                parts.append(f"{current_temp}°C now")
            if values.get("feels"):
                parts.append(f"feels like {values['feels']}°C")
            if precip_now:
                parts.append(f"precipitation now: {precip_now}")
            message = (
                "Now: " + ". ".join(parts).rstrip(".") + "."
                if parts
                else "Current weather is not available from the weather device."
            )
            title = "Weather now"
            subtitle = " · ".join(parts) if parts else "Weather data incomplete"
        for item in (
            _metric("Condition", condition, "🌦️"),
            _metric("Temperature", f"{current_temp}°C" if current_temp else None, "🌡️"),
            _metric("Humidity", humidity, "💧"),
            _metric("Precipitation", precip_now, "🌧️"),
        ):
            if item:
                metrics.append(item)

    else:
        summary = values.get("summary")
        details = [
            detail
            for detail in (
                condition,
                f"{current_temp}°C" if current_temp else None,
                humidity,
                f"rain chance {today_chance}%" if today_chance not in (None, "") else None,
                f"rainfall {precip_now}" if precip_now else None,
            )
            if detail
        ]
        if summary:
            message = summary
        elif details:
            message = "Weather: " + " · ".join(details) + "."
        else:
            message = (
                "A weather device was found, but it did not expose readable weather data."
            )
        title = "Weather"
        subtitle = summary or " · ".join(details[:3]) or "Weather data incomplete"
        for item in (
            _metric("Condition", condition, "🌦️"),
            _metric("Temperature", f"{current_temp}°C" if current_temp else None, "🌡️"),
            _metric("Humidity", humidity, "💧"),
            _metric("Rain now", precip_now, "🌧️"),
        ):
            if item:
                metrics.append(item)

    return (
        message,
        display_payload(
            "weather",
            title,
            subtitle=subtitle,
            metrics=metrics,
            note=note,
        ),
    )
