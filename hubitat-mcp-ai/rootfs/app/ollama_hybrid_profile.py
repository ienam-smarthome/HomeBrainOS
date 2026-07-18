from __future__ import annotations

from typing import Any


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_hybrid_profile(options: dict[str, Any]) -> dict[str, Any]:
    """Resolve configured and effective Ollama models for upgraded installations.

    Home Assistant preserves an add-on's existing ``/data/options.json`` values when
    a new release changes defaults. Older HomeBrain installations therefore retain
    ``ollama_model: qwen3.5:4b`` even after the Cloud profile is installed.  The
    explicit ``ollama_prefer_cloud_response`` switch makes the intended behaviour
    unambiguous: when enabled, the registered Cloud tag is the effective response
    and routine model, while Qwen remains the planner and local fallback.
    """

    configured_response = str(
        options.get("ollama_model") or "gemma4:31b-cloud"
    ).strip()
    cloud_model = str(
        options.get("ollama_cloud_model") or "gemma4:31b-cloud"
    ).strip()
    local_fallback = str(
        options.get("ollama_local_fallback_model") or "qwen3.5:4b"
    ).strip()
    planner_model = str(
        options.get("ollama_planner_model") or local_fallback or "qwen3.5:4b"
    ).strip()
    configured_routine = str(
        options.get("ollama_routine_model") or configured_response
    ).strip()
    cloud_enabled = _as_bool(options.get("ollama_cloud_enabled"), True)
    prefer_cloud = _as_bool(
        options.get("ollama_prefer_cloud_response"),
        True,
    )

    use_cloud = bool(cloud_enabled and prefer_cloud and cloud_model)
    effective_response = cloud_model if use_cloud else configured_response
    effective_routine = cloud_model if use_cloud else configured_routine

    return {
        "configured_response_model": configured_response,
        "effective_response_model": effective_response,
        "configured_routine_model": configured_routine,
        "effective_routine_model": effective_routine,
        "planner_model": planner_model,
        "cloud_enabled": cloud_enabled,
        "prefer_cloud_response": prefer_cloud,
        "cloud_model": cloud_model,
        "local_fallback_model": local_fallback,
        "legacy_saved_model_overridden": bool(
            use_cloud
            and configured_response
            and configured_response.lower() != effective_response.lower()
        ),
    }


__all__ = ["resolve_hybrid_profile"]
