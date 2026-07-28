from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


DEFAULT_TRACE_PATH = Path("/data/homebrain-request-traces.json")


def _safe_rows(value: Any, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = [dict(item) for item in value if isinstance(item, dict)]
    return rows[: max(1, int(limit))]


def install_persistent_request_diagnostics(
    store: Any,
    *,
    path: Path = DEFAULT_TRACE_PATH,
) -> dict[str, Any]:
    """Persist the existing bounded request trace store under Home Assistant /data.

    The request tracer remains authoritative. This adapter only reloads its safe,
    already-redacted summary rows at startup and writes the same bounded rows after
    each completed request. Failure to read or write diagnostics never blocks a
    HomeBrain request.
    """

    limit = int(getattr(store, "limit", 20) or 20)
    status: dict[str, Any] = {
        "enabled": True,
        "path": str(path),
        "loaded_count": 0,
        "write_count": 0,
        "load_error": None,
        "write_error": None,
    }

    try:
        loaded = _safe_rows(json.loads(path.read_text(encoding="utf-8")), limit=limit)
        for item in reversed(loaded):
            store.add(item)
        status["loaded_count"] = len(loaded)
    except FileNotFoundError:
        pass
    except Exception as exc:  # diagnostics must never break startup
        status["load_error"] = f"{type(exc).__name__}: {str(exc).strip()}"

    original_add: Callable[[dict[str, Any]], None] = store.add

    def persistent_add(item: dict[str, Any]) -> None:
        original_add(item)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = store.recent()
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            temporary.replace(path)
            status["write_count"] += 1
            status["write_error"] = None
        except Exception as exc:  # diagnostics must never break a request
            status["write_error"] = f"{type(exc).__name__}: {str(exc).strip()}"

    store.add = persistent_add
    store.persistence_status = status
    return status


__all__ = [
    "DEFAULT_TRACE_PATH",
    "install_persistent_request_diagnostics",
]
