from __future__ import annotations

import asyncio
import time
from typing import Any

from ollama_agent_fast import OllamaMCPAgent as BaseOllamaMCPAgent
from ollama_agent_fast import OllamaUnavailable


class OllamaMCPAgent(BaseOllamaMCPAgent):
    """Ollama agent with retry and short grace period for transient health failures."""

    async def health(self, force: bool = False) -> dict[str, Any]:
        now = time.time()
        if not force and self._health_cache and now - self._health_cache[0] < 15:
            return dict(self._health_cache[1])
        if not self.base_url or not self.model:
            result = {"online": False, "error": "Ollama is not configured"}
            self._health_cache = (now, result)
            return result

        last_error: Exception | None = None
        timeout = max(5.0, self.health_timeout_seconds)
        for attempt in range(2):
            try:
                response = await self._http.get(
                    f"{self.base_url}/api/tags",
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                names = [
                    str(item.get("name") or item.get("model") or "")
                    for item in payload.get("models", [])
                    if isinstance(item, dict)
                ]
                model_present = self.model in names or any(
                    name.split(":")[0] == self.model.split(":")[0]
                    for name in names
                )
                result = {
                    "online": True,
                    "model": self.model,
                    "model_present": model_present,
                    "models": names[:20],
                }
                self._last_online_health = (now, dict(result))
                self._health_cache = (now, result)
                return dict(result)
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.2)

        previous = getattr(self, "_last_online_health", None)
        if previous and now - previous[0] < 180:
            result = dict(previous[1])
            result["stale"] = True
            result["warning"] = str(last_error or "Temporary Ollama health failure")
            self._health_cache = (now, result)
            return result

        result = {
            "online": False,
            "error": str(last_error or "Ollama health check failed"),
            "model": self.model,
        }
        self._health_cache = (now, result)
        return dict(result)


__all__ = ["OllamaMCPAgent", "OllamaUnavailable"]
