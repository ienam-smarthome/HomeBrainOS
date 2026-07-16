from __future__ import annotations

import json
import re
from typing import Any

from ollama_agent_device_resolution import DeviceResolutionNaturalAgent
from ollama_agent_fast import OllamaUnavailable


_FINAL_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The complete user-facing answer only, with no analysis or hidden reasoning.",
        }
    },
    "required": ["answer"],
    "additionalProperties": False,
}

_REASONING_PATTERNS = (
    r"<think>",
    r"\bthe user (?:asked|wants|requested)\b",
    r"\bi have (?:the )?verified .* evidence\b",
    r"\bthe evidence (?:shows|contains|says|indicates)\b",
    r"\blet me (?:check|parse|think|tackle|analyse|analyze|work)\b",
    r"\bfirst,? i (?:need|should|will)\b",
    r"\bnext,? i (?:need|should|will)\b",
    r"\bwait,? (?:the user|i need|the evidence)\b",
    r"\bi should (?:answer|highlight|mention|focus|summarise|summarize)\b",
    r"\bso the key points\b",
    r"^analysis\s*:",
)


class FinalAnswerNaturalAgent(DeviceResolutionNaturalAgent):
    """Natural agent that never exposes a model's private working text.

    Qwen thinking is disabled both through Ollama's ``think`` request field and a
    ``/no_think`` prompt instruction. Final synthesis also uses Ollama structured
    output so only a validated ``answer`` string is accepted. If a model still
    emits analysis, a truncated completion, or malformed JSON, the existing
    verified MCP fallback is used instead of showing internal reasoning.
    """

    async def _chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
        temperature: float,
    ) -> dict[str, Any]:
        # Planning calls still need native tool_calls and therefore use the base
        # implementation unchanged. Only final user-facing synthesis is forced
        # through a strict answer schema.
        if tools:
            return await super()._chat(
                model=model,
                messages=messages,
                tools=tools,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )

        final_messages = self._final_only_messages(messages)
        try:
            body = await self._structured_final_chat(
                model=model,
                messages=final_messages,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=max(160, num_predict),
            )
            answer = self._extract_final_answer(body, require_json=True)
        except OllamaUnavailable as structured_error:
            # Older Ollama builds may not support JSON-schema output. Keep a
            # compatibility path, but still reject any visible chain-of-thought.
            try:
                body = await super()._chat(
                    model=model,
                    messages=final_messages,
                    tools=None,
                    timeout_seconds=timeout_seconds,
                    num_ctx=num_ctx,
                    num_predict=max(160, num_predict),
                    temperature=0.0,
                )
                answer = self._extract_final_answer(body, require_json=False)
            except Exception as fallback_error:
                raise OllamaUnavailable(
                    f"Final-answer generation failed: {structured_error}; {fallback_error}"
                ) from fallback_error

        clean_body = dict(body)
        message = dict(clean_body.get("message") or {})
        message["content"] = answer
        message.pop("thinking", None)
        clean_body["message"] = message
        return clean_body

    async def _structured_final_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": _FINAL_ANSWER_SCHEMA,
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": 0,
            },
        }
        try:
            response = await self._http.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise RuntimeError("Ollama returned a non-object response")
            return body
        except Exception as exc:
            text = str(exc) or exc.__class__.__name__
            if "timeout" in text.lower() or "timed out" in text.lower():
                raise OllamaUnavailable(
                    f"Ollama model {model} timed out after {timeout_seconds:g} seconds"
                ) from exc
            raise OllamaUnavailable(
                f"Ollama structured final answer failed for {model}: {text}"
            ) from exc

    @classmethod
    def _final_only_messages(
        cls,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        instruction = (
            "/no_think\n"
            "Return only the final answer for the user. Do not reveal analysis, planning, "
            "evidence parsing, hidden reasoning, or phrases such as 'the user asked'. "
            "The response must match the supplied JSON schema exactly: "
            '{"answer":"complete user-facing answer"}.'
        )
        cleaned: list[dict[str, Any]] = []
        system_found = False
        for raw in messages:
            item = dict(raw)
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
            if role == "assistant" and cls._looks_like_reasoning(content):
                # Do not feed a leaked reasoning response back into the next turn.
                continue
            if role == "system":
                system_found = True
                item["content"] = (content.rstrip() + "\n\n" + instruction).strip()
            cleaned.append(item)
        if not system_found:
            cleaned.insert(0, {"role": "system", "content": instruction})
        return cleaned

    @classmethod
    def _extract_final_answer(
        cls,
        body: dict[str, Any],
        *,
        require_json: bool,
    ) -> str:
        if str(body.get("done_reason") or "").lower() == "length":
            raise OllamaUnavailable("Ollama final answer was truncated")

        message = body.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise OllamaUnavailable("Ollama returned no final answer")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
        answer = ""
        try:
            decoded = json.loads(content)
            if isinstance(decoded, dict):
                answer = str(decoded.get("answer") or "").strip()
        except Exception:
            if require_json:
                raise OllamaUnavailable("Ollama did not follow the final-answer JSON schema")

        if not answer and not require_json:
            answer = cls._strip_thinking_blocks(content)

        if not answer:
            raise OllamaUnavailable("Ollama returned an empty final answer")
        if cls._looks_like_reasoning(answer):
            raise OllamaUnavailable("Ollama exposed internal reasoning instead of a final answer")
        if cls._looks_incomplete(answer):
            raise OllamaUnavailable("Ollama returned an incomplete final answer")
        return answer.strip()

    @staticmethod
    def _strip_thinking_blocks(value: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", value, flags=re.I | re.S).strip()
        if "</think>" in text.lower():
            text = re.split(r"</think>", text, flags=re.I)[-1].strip()
        final_match = re.search(
            r"(?:^|\n)(?:final answer|answer)\s*:\s*(.+)$",
            text,
            flags=re.I | re.S,
        )
        return final_match.group(1).strip() if final_match else text

    @staticmethod
    def _looks_like_reasoning(value: str) -> bool:
        text = str(value or "").strip().lower()
        return any(re.search(pattern, text, flags=re.I | re.S) for pattern in _REASONING_PATTERNS)

    @staticmethod
    def _looks_incomplete(value: str) -> bool:
        text = str(value or "").rstrip()
        if len(text) < 2:
            return True
        trailing = (
            ":",
            "-",
            "•",
            ",",
            " and",
            " or",
            " but",
            " because",
            " the",
            " a",
        )
        return any(text.lower().endswith(suffix) for suffix in trailing)


__all__ = ["FinalAnswerNaturalAgent", "OllamaUnavailable"]
