from __future__ import annotations

import ipaddress
import re
from typing import Any

import httpx


_PERCENT_PATTERNS = (
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
    """Parse Hubitat's local /hub/cpuInfo text without inventing a percentage."""
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

    for pattern in _PERCENT_PATTERNS:
        match = re.search(pattern, text, flags=re.I)
        if match:
            percent = float(match.group(1))
            result.update(
                {
                    "available": True,
                    "mode": "percent",
                    "percent": percent,
                    "value": f"{percent:g}%",
                    "label": "CPU load",
                }
            )
            return result

    processors_match = re.search(r"processors?\s*[:=]?\s*(\d+)", text, flags=re.I)
    load_match = re.search(
        r"load\s+average\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.I,
    )
    if load_match:
        load_average = float(load_match.group(1))
        processors = int(processors_match.group(1)) if processors_match else None
        result.update(
            {
                "available": True,
                "mode": "load-average",
                "load_average": load_average,
                "processors": processors,
                "value": f"{load_average:g}",
                "label": "CPU load avg",
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
