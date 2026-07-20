from __future__ import annotations

from typing import Any

import ai_evidence_planner as planner_module
from control_focus_mode import install_control_focus_mode
from semantic_metric_comparison_live import SemanticMetricComparisonExecutor


_EXTRA_HOME_DOMAIN_TERMS = (
    "electricity",
    "electrical",
    "bathroom",
    "toilet",
    "kitchen",
    "living room",
    "bedroom",
    "hallway",
    "ventilation",
    "dehumidifier",
    "air purifier",
    "camera",
    "appliance",
)
_ORIGINAL_AI_EVIDENCE_QUERY = planner_module.is_ai_evidence_query


def install_ai_evidence_domains() -> tuple[str, ...]:
    """Install broad evidence domains or the safer default Control Focus scope.

    Control Focus is enabled by default for release 0.7.1. It keeps the proven
    control and verified-read routes, adds a deterministic current-power summary,
    and prevents the later AI Evidence Planner wrapper from capturing broad
    questions. Disabling ``control_focus_mode_enabled`` restores the 0.7.0 broad
    evidence-planner behaviour without removing its code or settings.
    """

    existing = tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))
    merged = tuple(dict.fromkeys((*existing, *_EXTRA_HOME_DOMAIN_TERMS)))
    planner_module._HOME_DOMAIN_TERMS = merged

    import app as application

    control_focus_enabled = application.option_bool("control_focus_mode_enabled", True)
    if control_focus_enabled:
        # AIEvidencePlanner.matches resolves this module global at runtime. Keeping
        # it false prevents the outer planner wrapper from bypassing Control Focus.
        planner_module.is_ai_evidence_query = lambda _query: False
        metric_executor = SemanticMetricComparisonExecutor(application.fallback)
        install_control_focus_mode(
            application,
            metric_executor,
            enabled=True,
            allow_verified_reads=application.option_bool(
                "control_focus_allow_verified_reads",
                True,
            ),
        )
    else:
        planner_module.is_ai_evidence_query = _ORIGINAL_AI_EVIDENCE_QUERY
    return merged


def installed_domain_terms() -> tuple[str, ...]:
    return tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))


__all__ = [
    "install_ai_evidence_domains",
    "installed_domain_terms",
]
