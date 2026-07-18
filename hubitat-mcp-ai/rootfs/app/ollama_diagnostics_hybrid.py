from __future__ import annotations

import json
from typing import Any, Awaitable, Callable


DiagnosticsHandler = Callable[[bool], Awaitable[dict[str, Any]]]


def _state(value: Any) -> str:
    return str(value or "idle").replace("-", " ").title()


def install_hybrid_ollama_diagnostics(application: Any) -> DiagnosticsHandler:
    """Show Cloud, planner and fallback readiness independently.

    The legacy diagnostics card only displayed ``runtime.model``. On upgraded
    installations that value could still be the saved local Qwen tag even when the
    Cloud tag was registered and preferred. This wrapper reports the effective
    response model and all hybrid components separately.
    """

    original: DiagnosticsHandler = application.build_ollama_diagnostics

    async def hybrid_diagnostics(force: bool = False) -> dict[str, Any]:
        answer = dict(await original(force=force))
        runtime = dict(answer.get("runtime") or {})
        profile = dict(getattr(application, "ollama_hybrid_profile", {}) or {})

        server_online = bool(runtime.get("online"))
        cloud_model = str(
            runtime.get("cloud_model")
            or profile.get("cloud_model")
            or "gemma4:31b-cloud"
        )
        cloud_present = bool(runtime.get("cloud_present"))
        fallback_model = str(
            runtime.get("local_fallback_model")
            or profile.get("local_fallback_model")
            or "qwen3.5:4b"
        )
        fallback_present = bool(runtime.get("local_fallback_present"))
        planner_model = str(
            runtime.get("planner_model")
            or profile.get("planner_model")
            or fallback_model
        )
        response_model = str(
            profile.get("effective_response_model")
            or runtime.get("preferred_response_model")
            or runtime.get("model")
            or cloud_model
        )
        configured_model = str(
            profile.get("configured_response_model")
            or application.OPTIONS.get("ollama_model")
            or response_model
        )
        prefer_cloud = bool(profile.get("prefer_cloud_response", True))
        last_agent = dict(runtime.get("last_agent") or {})
        last_state = _state(last_agent.get("state"))

        cloud_status = "Ready" if cloud_present else "Unavailable"
        fallback_status = "Ready" if fallback_present else "Missing"
        response_status = (
            "Cloud"
            if response_model.lower() == cloud_model.lower() and cloud_present
            else "Local"
        )

        lines = [
            f"Ollama server: {'Online' if server_online else 'Offline'}",
            f"Effective response model: {response_model} ({response_status.lower()})",
            f"Cloud model: {cloud_model} ({cloud_status.lower()})",
            f"Planner model: {planner_model}",
            f"Local fallback: {fallback_model} ({fallback_status.lower()})",
            f"Last agent state: {last_state}",
        ]
        if configured_model.lower() != response_model.lower():
            lines.append(
                f"Saved response setting: {configured_model} (overridden by Prefer Cloud response)"
            )
        if last_agent.get("error"):
            lines.append(f"Last agent error: {last_agent['error']}")

        migration_note = ""
        if profile.get("legacy_saved_model_overridden"):
            migration_note = (
                f" The older saved response value {configured_model} is being safely "
                f"overridden because Prefer Cloud response is on. Turn that option off "
                f"only when local-only synthesis is intended."
            )

        answer.update(
            {
                "success": server_online and bool(cloud_present or fallback_present),
                "route": "system",
                "intent": "ollama-diagnostics",
                "message": "\n".join(lines),
                "model": response_model,
                "runtime": runtime,
                "hybrid_profile": profile,
                "display": {
                    "kind": "ollama-diagnostics",
                    "title": "Ollama hybrid diagnostics",
                    "subtitle": (
                        f"Cloud {cloud_status.lower()} · response {response_model}"
                    ),
                    "metrics": [
                        {
                            "label": "Server",
                            "value": "Online" if server_online else "Offline",
                            "icon": "🟢" if server_online else "🔴",
                        },
                        {
                            "label": "Cloud",
                            "value": cloud_status,
                            "icon": "☁️",
                        },
                        {
                            "label": "Response",
                            "value": response_model,
                            "icon": "🧠",
                        },
                        {
                            "label": "Planner",
                            "value": planner_model,
                            "icon": "🧭",
                        },
                        {
                            "label": "Fallback",
                            "value": fallback_model,
                            "icon": "🛟",
                        },
                        {
                            "label": "Last agent",
                            "value": last_state,
                            "icon": "🤖",
                        },
                    ],
                    "items": [],
                    "note": (
                        "Cloud registration and local availability are read from Ollama "
                        "/api/tags; loaded local models are read from /api/ps."
                        + migration_note
                    ),
                },
                "technical": json.dumps(
                    {
                        "runtime": runtime,
                        "hybrid_profile": profile,
                        "configured_response_model": configured_model,
                        "effective_response_model": response_model,
                        "prefer_cloud_response": prefer_cloud,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            }
        )
        return answer

    application.build_ollama_diagnostics = hybrid_diagnostics
    application.hybrid_ollama_diagnostics = hybrid_diagnostics
    return hybrid_diagnostics


__all__ = ["install_hybrid_ollama_diagnostics"]
