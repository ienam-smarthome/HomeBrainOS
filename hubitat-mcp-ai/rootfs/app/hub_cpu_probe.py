from __future__ import annotations

import ipaddress
import re
from typing import Any

import httpx


_PERCENT_PATTERNS = (
    # Hub Info-style output: "CPU Load/Load% 0.6 / 15.0 %".
    r"cpu\s*load\s*/\s*load\s*%?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*%",
    r"(?:cpu(?:\s+(?:usage|load))?|usage)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*%",
    r"([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:cpu|usage|load)",
)


def _private_host(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^https?://", "", text, flags=re.I).split("/", 1)[0]
    text = text.split(":", 1)[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if not (address.is_private or address.is_link_local or address.is_loopback):
        return None
    return str(address)


def parse_cpu_info(value: str) -> dict[str, Any]:
    """Parse Hubitat's local /hub/cpuInfo text and report CPU percentage.

    Hubitat installations expose CPU data in more than one format. Some return an
    explicit percentage, some return ``load/load%`` and others only return a
    one-minute load average plus processor count. In the final case the percentage
    is calculated as ``load_average / processors * 100`` and clearly marked as a
    derived value in technical details.
    """
    text = str(value or "").strip()
    result: dict[str, Any] = {
        "available": False,
        "mode": "unavailable",
        "raw": text[:1200],
    }
    if not text:
        result["error"] = "The hub returned an empty CPU response."
        return result

    if "<html" in text.lower() or "login" in text.lower():
        result["error"] = "The hub CPU endpoint requires local hub authentication."
        return result

    for index, pattern in enumerate(_PERCENT_PATTERNS):
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue

        if index == 0:
            load_average = float(match.group(1))
            percent = float(match.group(2))
            result.update(
                {
                    "available": True,
                    "mode": "percent",
                    "load_average": load_average,
                    "percent": percent,
                    "value": f"{percent:g}%",
                    "label": "CPU load",
                    "summary": f"{load_average:g} / {percent:g}%",
                    "percent_source": "hub-reported-load-percent",
                    "derived_percent": False,
                }
            )
        else:
            percent = float(match.group(1))
            result.update(
                {
                    "available": True,
                    "mode": "percent",
                    "percent": percent,
                    "value": f"{percent:g}%",
                    "label": "CPU load",
                    "percent_source": "hub-reported-percent",
                    "derived_percent": False,
                }
            )
        return result

    processors_match = re.search(
        r"(?:processors?|cpu\s*cores?|cores?)\s*[:=]?\s*(\d+)",
        text,
        flags=re.I,
    )
    load_match = re.search(
        r"(?:1\s*(?:min(?:ute)?|m)\s*)?load(?:\s+average)?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.I,
    )
    if load_match:
        load_average = float(load_match.group(1))
        processors = int(processors_match.group(1)) if processors_match else None
        percent = (
            min(100.0, max(0.0, (load_average / processors) * 100.0))
            if processors and processors > 0
            else None
        )
        result.update(
            {
                "available": True,
                "mode": "percent" if percent is not None else "load-average",
                "load_average": load_average,
                "processors": processors,
                "percent": percent,
                "value": f"{percent:.1f}%" if percent is not None else f"{load_average:g}",
                "label": "CPU load" if percent is not None else "CPU load avg",
                "summary": (
                    f"{load_average:g} / {percent:.1f}%"
                    if percent is not None
                    else f"{load_average:g}"
                ),
                "percent_source": "derived-from-load-and-processors" if percent is not None else None,
                "derived_percent": percent is not None,
            }
        )
        return result

    result["error"] = "The hub CPU endpoint returned an unrecognised format."
    return result


async def probe_hub_cpu(
    local_ip: Any,
    *,
    timeout_seconds: float = 2.5,
) -> dict[str, Any]:
    host = _private_host(local_ip)
    if not host:
        return {
            "available": False,
            "mode": "unavailable",
            "error": "A private Hubitat local IP was not available from MCP.",
        }

    url = f"http://{host}/hub/cpuInfo"
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.get(url, timeout=max(0.5, float(timeout_seconds)))
            if response.status_code in {301, 302, 303, 307, 308, 401, 403}:
                return {
                    "available": False,
                    "mode": "unavailable",
                    "url": url,
                    "status_code": response.status_code,
                    "error": "The hub CPU endpoint is protected by local hub authentication.",
                }
            response.raise_for_status()
            parsed = parse_cpu_info(response.text)
            parsed["url"] = url
            parsed["status_code"] = response.status_code
            return parsed
    except Exception as exc:
        return {
            "available": False,
            "mode": "unavailable",
            "url": url,
            "error": f"Hub CPU probe failed: {exc}",
        }


__all__ = ["parse_cpu_info", "probe_hub_cpu"]
