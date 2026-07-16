from __future__ import annotations

import asyncio
import time
from typing import Any

from ollama_agent_fast import OllamaUnavailable
from ollama_agent_resilient import OllamaMCPAgent as ResilientOllamaMCPAgent


class OllamaMCPAgent(ResilientOllamaMCPAgent):
    """Ollama agent that tracks server reachability and model inference separately."""

    def __init__(
        self,
        *args: Any,
        inference_probe_timeout_seconds: float = 8,
        inference_warmup_timeout_seconds: float = 90,
        inference_failure_ttl_seconds: float = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.inference_probe_timeout_seconds = max(
            2.0,
            float(inference_probe_timeout_seconds),
        )
        self.inference_warmup_timeout_seconds = max(
            self.inference_probe_timeout_seconds,
            float(inference_warmup_timeout_seconds),
        )
        self.inference_failure_ttl_seconds = max(
            10.0,
            float(inference_failure_ttl_seconds),
        )
        self._inference_cache: tuple[float, dict[str, Any]] | None = None
        self._inference_probe_lock = asyncio.Lock()
        self._inference_probe_task: asyncio.Task[dict[str, Any]] | None = None

    def inference_probe_running(self) -> bool:
        return bool(
            self._inference_probe_task
            and not self._inference_probe_task.done()
        )

    def inference_status(self) -> dict[str, Any]:
        now = time.time()
        running = self.inference_probe_running()
        if not self._inference_cache:
            return {
                "ready": None,
                "state": "warming" if running else "unknown",
                "model": self.model,
                "message": (
                    "The Ollama model is warming up in the background."
                    if running
                    else "Model inference has not been checked yet."
                ),
            }

        checked_at, status = self._inference_cache
        age_seconds = round(max(0.0, now - checked_at), 1)

        if (
            status.get("ready") is False
            and age_seconds >= self.inference_failure_ttl_seconds
        ):
            return {
                "ready": None,
                "state": "warming" if running else "retry-due",
                "model": self.model,
                "message": (
                    "The Ollama model is warming up in the background."
                    if running
                    else "The previous inference failure has expired; a background recheck is due."
                ),
                "source": status.get("source"),
                "elapsed_ms": status.get("elapsed_ms"),
                "error": status.get("error"),
                "previous_state": status.get("state"),
                "stale": True,
                "age_seconds": age_seconds,
            }

        result = dict(status)
        result["age_seconds"] = age_seconds
        return result

    def inference_probe_due(self) -> bool:
        if self.inference_probe_running():
            return False
        status = self.inference_status()
        if status.get("ready") is None:
            return True
        if status.get("ready") is False:
            return False
        return float(status.get("age_seconds") or 0) >= 300

    def schedule_inference_probe(
        self,
        *,
        force: bool = False,
        timeout_seconds: float | None = None,
    ) -> asyncio.Task[dict[str, Any]] | None:
        """Start one non-blocking inference probe when a recheck is due."""
        if not force and not self.inference_probe_due():
            return self._inference_probe_task
        if self.inference_probe_running():
            return self._inference_probe_task
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None

        self._inference_probe_task = loop.create_task(
            self.probe_inference(
                force=force,
                timeout_seconds=timeout_seconds,
            )
        )
        return self._inference_probe_task

    def recent_inference_failure(self) -> dict[str, Any] | None:
        if not self._inference_cache:
            return None
        checked_at, status = self._inference_cache
        if status.get("ready") is not False:
            return None
        if time.time() - checked_at >= self.inference_failure_ttl_seconds:
            return None
        return self.inference_status()

    def record_inference_success(
        self,
        elapsed_ms: int | None = None,
        source: str = "chat",
    ) -> dict[str, Any]:
        result = {
            "ready": True,
            "state": "ready",
            "model": self.model,
            "message": f"{self.model} is responding to chat requests.",
            "source": source,
            "elapsed_ms": elapsed_ms,
            "error": None,
        }
        self._inference_cache = (time.time(), result)
        return dict(result)

    def record_inference_failure(
        self,
        error: str,
        *,
        state: str = "error",
        elapsed_ms: int | None = None,
        source: str = "chat",
    ) -> dict[str, Any]:
        clean_error = str(error or "Model inference failed").strip()
        result = {
            "ready": False,
            "state": state,
            "model": self.model,
            "message": self._friendly_inference_message(state, clean_error),
            "source": source,
            "elapsed_ms": elapsed_ms,
            "error": clean_error,
            "retry_after_seconds": int(self.inference_failure_ttl_seconds),
        }
        self._inference_cache = (time.time(), result)
        return dict(result)

    async def probe_inference(
        self,
        force: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        recent_failure = self.recent_inference_failure()
        if recent_failure and not force:
            return recent_failure
        current = self.inference_status()
        if (
            current.get("ready") is True
            and not force
            and current.get("age_seconds", 999) < 300
        ):
            return current

        async with self._inference_probe_lock:
            recent_failure = self.recent_inference_failure()
            if recent_failure and not force:
                return recent_failure
            current = self.inference_status()
            if (
                current.get("ready") is True
                and not force
                and current.get("age_seconds", 999) < 300
            ):
                return current

            server = await self.health(force=force)
            if not server.get("online"):
                return self.record_inference_failure(
                    server.get("error") or "Ollama server is unreachable",
                    state="server-offline",
                    source="probe",
                )

            allowed_timeout = max(
                2.0,
                float(timeout_seconds or self.inference_probe_timeout_seconds),
            )
            started = time.perf_counter()
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Reply with exactly: ready",
                    }
                ],
                "stream": False,
                "think": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "num_ctx": 1024,
                    "num_predict": 8,
                    "temperature": 0,
                },
            }
            try:
                response = await self._http.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=allowed_timeout,
                )
                response.raise_for_status()
                body = response.json()
                content = str((body.get("message") or {}).get("content") or "").strip()
                if not content:
                    raise RuntimeError("Ollama returned an empty chat response")
                return self.record_inference_success(
                    round((time.perf_counter() - started) * 1000),
                    source="probe",
                )
            except (TimeoutError, asyncio.TimeoutError) as exc:
                return self.record_inference_failure(
                    str(exc) or "Inference readiness probe timed out",
                    state="timeout",
                    elapsed_ms=round((time.perf_counter() - started) * 1000),
                    source="probe",
                )
            except Exception as exc:
                state = "timeout" if "timed out" in str(exc).lower() else "error"
                return self.record_inference_failure(
                    str(exc),
                    state=state,
                    elapsed_ms=round((time.perf_counter() - started) * 1000),
                    source="probe",
                )

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        recent_failure = self.recent_inference_failure()
        if recent_failure:
            raise OllamaUnavailable(recent_failure["message"])
        if self.inference_probe_running() and self.inference_status().get("ready") is not True:
            raise OllamaUnavailable(
                "The Ollama model is warming up in the background."
            )

        started = time.perf_counter()
        try:
            answer = await super().answer(query, history)
        except OllamaUnavailable as exc:
            state = "timeout" if "timed out" in str(exc).lower() else "error"
            self.record_inference_failure(
                str(exc),
                state=state,
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
            raise
        except Exception as exc:
            self.record_inference_failure(
                str(exc),
                state="error",
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
            raise

        self.record_inference_success(
            int(answer.get("elapsed_ms") or round((time.perf_counter() - started) * 1000)),
        )
        return answer

    def fallback_reason(self) -> str:
        server_online = bool(
            self._health_cache
            and isinstance(self._health_cache[1], dict)
            and self._health_cache[1].get("online")
        )
        inference = self.inference_status()
        if server_online and inference.get("state") == "warming":
            return (
                f"Ollama server is online and {self.model} is warming up in the background. "
                "The local MCP fallback answered meanwhile."
            )
        if server_online and inference.get("ready") is False:
            if inference.get("state") == "timeout":
                return (
                    f"Ollama server is online, but {self.model} did not respond within the "
                    "allowed time. The local MCP fallback answered instead."
                )
            return (
                f"Ollama server is online, but {self.model} could not complete the chat "
                "request. The local MCP fallback answered instead."
            )
        if server_online and inference.get("state") == "retry-due":
            return (
                "The previous Ollama inference failure has expired and is being rechecked. "
                "The local MCP fallback answered meanwhile."
            )
        if not server_online:
            return "Ollama server is currently unreachable. The local MCP fallback answered instead."
        return "The local MCP fallback answered instead of Ollama."

    @staticmethod
    def _friendly_inference_message(state: str, error: str) -> str:
        if state == "timeout":
            return "Model inference timed out."
        if state == "server-offline":
            return "Ollama server is unreachable."
        return f"Model inference failed: {error}"


__all__ = ["OllamaMCPAgent", "OllamaUnavailable"]
