"""On-demand network reachability checks from the add-on host.

Read-only: one bounded probe set per request (the UI asks when System Health opens and about once a minute while it stays open). It tests
what the add-on host can reach (internet, DNS, the Hubitat hub, an optional
router address). It does not test the hub's own internet access.
"""
from __future__ import annotations

import asyncio
import shutil
import socket
import time
from typing import Awaitable, Callable
from urllib.parse import urlsplit

TIMEOUT = 2.5
INTERNET_TARGETS = (("Cloudflare", "1.1.1.1", 443), ("Google DNS", "8.8.8.8", 53))
ROUTER_TCP_PORTS = (80, 443, 53, 22)

Connect = Callable[[str, int, float], Awaitable[float | None]]


async def tcp_connect_ms(host: str, port: int, timeout: float = TIMEOUT) -> float | None:
    started = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, asyncio.TimeoutError):
        return None
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return round((time.monotonic() - started) * 1000, 1)


async def ping_ms(host: str, timeout: float = TIMEOUT) -> float | None:
    binary = shutil.which("ping")
    if not binary:
        return None
    started = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            binary, "-c", "1", "-W", str(max(1, int(timeout))), host,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        code = await asyncio.wait_for(proc.wait(), timeout + 1)
    except (OSError, asyncio.TimeoutError):
        return None
    return round((time.monotonic() - started) * 1000, 1) if code == 0 else None


def clean_host(value: str) -> str:
    """Accept '192.168.1.1', 'http://192.168.1.1/', '192.168.1.1:80' and return the host."""
    text = (value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "//" + text
    try:
        return urlsplit(text).hostname or ""
    except ValueError:
        return ""


def _host_port(url: str) -> tuple[str, int] | None:
    try:
        parts = urlsplit(url)
        if not parts.hostname:
            return None
        return parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None


async def _dns_ok() -> bool:
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(loop.run_in_executor(
            None, socket.getaddrinfo, "example.com", 443), TIMEOUT + 1)
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _check(name: str, ok: bool, ms: float | None, method: str) -> dict:
    return {"name": name, "ok": ok, "ms": ms, "method": method}


async def network_status(hub_url: str = "", router_host: str = "",
                         connect: Connect = tcp_connect_ms,
                         ping: Callable[[str], Awaitable[float | None]] = ping_ms,
                         dns: Callable[[], Awaitable[bool]] = _dns_ok) -> dict:
    router_host = clean_host(router_host)
    hub = _host_port(hub_url) if hub_url else None

    async def internet(label, host, port):
        ms = await connect(host, port, TIMEOUT)
        return _check(f"Internet · {label}", ms is not None, ms, f"tcp {port}")

    async def hub_check():
        ms = await connect(hub[0], hub[1], TIMEOUT)
        return _check("Hubitat hub", ms is not None, ms, f"tcp {hub[1]}")

    async def router_check():
        ms = await ping(router_host)
        if ms is not None:
            return _check("Router", True, ms, "ping")
        found = await asyncio.gather(*[connect(router_host, p, TIMEOUT) for p in ROUTER_TCP_PORTS])
        for port, ms in zip(ROUTER_TCP_PORTS, found):
            if ms is not None:
                return _check("Router", True, ms, f"tcp {port}")
        tried = "ping, tcp " + "/".join(str(p) for p in ROUTER_TCP_PORTS)
        return _check("Router", False, None, f"no answer to {tried}")

    tasks = [internet(*t) for t in INTERNET_TARGETS]
    if hub:
        tasks.append(hub_check())
    if router_host:
        tasks.append(router_check())
    results = await asyncio.gather(*tasks, dns())
    dns_ok = results[-1]
    checks = list(results[:-1])
    checks.append(_check("DNS lookup", bool(dns_ok), None, "resolver"))
    by = {c["name"]: c for c in checks}
    net = [c for c in checks if c["name"].startswith("Internet")]
    internet_ok = any(c["ok"] for c in net)
    hub_ok = by["Hubitat hub"]["ok"] if "Hubitat hub" in by else None
    router_ok = by["Router"]["ok"] if "Router" in by else None
    if internet_ok and dns_ok and router_ok is False:
        summary, level = ("Internet reachable; router address did not answer (it may block ping and "
                          "these ports, or the address in network_router_host may be wrong)"), "warn"
    elif internet_ok and dns_ok:
        summary, level = "Internet reachable", "ok"
    elif internet_ok:
        summary, level = "Internet reachable by address, but DNS lookup failed", "warn"
    elif router_ok is True:
        summary, level = "Router reachable, internet not reachable", "bad"
    elif router_ok is False:
        summary, level = "Router not reachable from this add-on", "bad"
    else:
        summary, level = "Internet not reachable (no router address configured to narrow it down)", "bad"
    if hub_ok is False:
        summary += "; Hubitat hub not reachable"
        level = "bad"
    return {"read_only": True, "level": level, "summary": summary, "checks": checks,
            "checked_at": time.time(), "router_configured": bool(router_host),
            "scope": ("Checked from the add-on host while this tab is open. This does not test the "
                      "hub's own internet access; a Hubitat Hub Ping device can do that.")}
