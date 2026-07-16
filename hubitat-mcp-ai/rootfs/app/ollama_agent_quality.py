from __future__ import annotations

import json
import re
import time
from typing import Any

from ollama_agent_fast import OllamaUnavailable
from ollama_agent_natural import NaturalHubitatOllamaAgent
from routing_policy import requires_planner


class QualityNaturalHubitatOllamaAgent(NaturalHubitatOllamaAgent):
    """Natural Ollama agent with verified evidence-first routine answers.

    Routine read-only questions first ask the existing MCP fallback provider for a
    compact, authoritative evidence package. Ollama still writes the user-facing
    answer, but the slow tool-planning pass is skipped when verified context is
    already available. Complex questions and non-basic controls use the full MCP
    planner.
    """

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        history = history or []
        if requires_planner(query):
            return await super().answer(query, history)

        verified = await self._fallback_evidence(query)
        if verified is not None:
            return await self._answer_from_verified_context(
                query=query,
                history=history,
                verified=verified,
            )
        return await super().answer(query, history)

    async def answer_with_planner(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Force the full MCP planner for ambiguous control resolution."""
        return await super().answer(query, history or [])

    def _resolve_planner_model(self, installed_models: list[str]) -> str:
        if self.configured_planner_model:
            if self._model_matches(self.configured_planner_model, installed_models):
                return self.configured_planner_model
            return self.model
        return self._preferred_family_model(installed_models)

    def _resolve_routine_model(self, installed_models: list[str]) -> str:
        if self.configured_routine_model:
            if self._model_matches(self.configured_routine_model, installed_models):
                return self.configured_routine_model
            return self.model
        return self._preferred_family_model(installed_models)

    def _preferred_family_model(self, installed_models: list[str]) -> str:
        """Prefer a smaller Qwen-family model, never an unrelated silent downgrade."""
        response_family = self.model.split(":", 1)[0].lower()
        broad_family = re.sub(r"\d.*$", "", response_family) or response_family
        candidates = [
            name
            for name in installed_models
            if name
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
            and (
                name.split(":", 1)[0].lower().startswith(broad_family)
                or (
                    response_family.startswith("qwen")
                    and name.split(":", 1)[0].lower().startswith("qwen")
                )
            )
        ]
        if not candidates:
            return self.model

        def size_key(name: str) -> tuple[float, int, str]:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            size = float(match.group(1)) if match else 999.0
            exact_family = 0 if name.split(":", 1)[0].lower() == response_family else 1
            return size, exact_family, name.lower()

        candidates.sort(key=size_key)
        return candidates[0]

    async def _answer_from_verified_context(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        verified: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        health = await self.health()
        if not health.get("online"):
            raise OllamaUnavailable(health.get("error") or "Ollama is offline")
        if health.get("model_present") is False:
            raise OllamaUnavailable(
                f"Configured Ollama model {self.model} is not installed."
            )

        installed = list(health.get("models") or [])
        response_model = self._resolve_routine_model(installed)
        evidence_text = self._compact_fallback_evidence(verified)
        timeout = min(
            self.response_timeout_seconds,
            self.routine_response_timeout_seconds,
            40.0,
        )

        self._last_agent_status = {
            "state": "synthesising",
            "planner_model": "verified-mcp-context",
            "response_model": response_model,
            "query": query[:200],
            "evidence_source": "verified-mcp-context",
            "started_at": time.time(),
        }

        synthesis_started = time.perf_counter()
        try:
            body = await self._chat(
                model=response_model,
                messages=self._verified_messages(
                    query=query,
                    history=history,
                    evidence=evidence_text,
                ),
                tools=None,
                timeout_seconds=timeout,
                num_ctx=min(self.num_ctx, 2048),
                num_predict=min(self.num_predict, 120),
                temperature=0.1,
            )
            content = str((body.get("message") or {}).get("content") or "").strip()
            if self._unreliable_verified_answer(query, content, evidence_text):
                raise OllamaUnavailable(
                    "Ollama added unsupported claims to verified Hubitat evidence."
                )
        except Exception as exc:
            phase_ms = {
                "mcp_context": 0,
                "synthesis": round((time.perf_counter() - synthesis_started) * 1000),
            }
            return self._compact_fallback_result(
                verified,
                started=started,
                planner_error=None,
                synthesis_error=str(exc),
                planner_model="verified-mcp-context",
                response_model=response_model,
                phase_ms=phase_ms,
            )

        elapsed = round((time.perf_counter() - started) * 1000)
        self.record_inference_success(elapsed, source="verified-natural-agent")
        self._last_agent_status = {
            "state": "ready",
            "planner_model": "verified-mcp-context",
            "response_model": response_model,
            "tools_used": ["verified_mcp_context"],
            "evidence_source": "verified-mcp-context",
            "phase_ms": {"synthesis": elapsed},
            "elapsed_ms": elapsed,
            "completed_at": time.time(),
        }
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "ollama-verified-natural-agent",
            "message": content,
            "model": response_model,
            "planner_model": "verified-mcp-context",
            "response_model": response_model,
            "tools_used": [
                {
                    "name": "verified_mcp_context",
                    "success": True,
                    "preview": evidence_text[:700],
                }
            ],
            "selected_tools": ["verified_mcp_context"],
            "evidence_source": "verified-mcp-context",
            "phase_ms": {"synthesis": elapsed},
            "elapsed_ms": elapsed,
        }

    @staticmethod
    def _verified_messages(
        *,
        query: str,
        history: list[dict[str, str]],
        evidence: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a concise, natural local smart-home assistant. Use only the "
                    "verified Hubitat evidence supplied below. It is complete enough to answer "
                    "the question. Never invent firmware, backups, timestamps, temperatures, "
                    "alerts, occupancy or device states. Hub internal temperature is not home "
                    "temperature. A zero or missing timestamp is not a real event. Lead with "
                    "what matters now, name important devices, and keep routine answers to two "
                    "to four short sentences. Do not offer a numbered menu or ask a follow-up "
                    "question unless the evidence is genuinely ambiguous."
                ),
            }
        ]
        for item in history[-2:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append(
                    {"role": str(item["role"]), "content": str(item["content"])}
                )
        messages.extend(
            [
                {"role": "user", "content": query},
                {
                    "role": "user",
                    "content": "Verified live Hubitat evidence:\n" + evidence,
                },
                {
                    "role": "user",
                    "content": "Answer the original question now using only that evidence.",
                },
            ]
        )
        return messages

    def _unreliable_verified_answer(
        self,
        query: str,
        content: str,
        evidence: str,
    ) -> bool:
        if not content or self._looks_like_tool_json(content):
            return True
        text = content.lower()
        evidence_lower = evidence.lower()
        blocked = (
            "epoch 0",
            "hub is still gathering data",
            "i don't have enough information",
            "i do not have enough information",
            "can't confirm device states",
            "cannot confirm device states",
        )
        if any(phrase in text for phrase in blocked):
            return True

        q = query.lower()
        is_home_overview = any(
            phrase in q
            for phrase in (
                "what's happening",
                "what is happening",
                "home status",
                "at home",
            )
        )
        if is_home_overview:
            for unsupported in ("firmware", "backup", "epoch"):
                if unsupported in text and unsupported not in evidence_lower:
                    return True
            if (
                re.search(r"\b4[0-9](?:\.\d+)?\s*(?:°\s*c|degrees? celsius)", text)
                and "temperature" not in evidence_lower
            ):
                return True
        return False


__all__ = ["QualityNaturalHubitatOllamaAgent", "OllamaUnavailable"]
