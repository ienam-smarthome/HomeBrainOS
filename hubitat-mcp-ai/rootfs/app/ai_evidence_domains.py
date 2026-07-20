from __future__ import annotations

from typing import Any

import ai_evidence_planner as planner_module
from control_focus_ai_fallback import install_control_focus_ai_fallback_scope
from control_focus_mode import install_control_focus_mode
from control_focus_octopus_energy import install_control_focus_octopus_energy
from control_focus_power_summary_safe import install_control_focus_power_summary_safe
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


def install_ai_evidence_domains(*, activate_runtime: bool = True) -> tuple[str, ...]:
    """Install broad evidence domains with a control-first, read-only AI fallback.

    Control Focus remains enabled by default. Proven controls and verified reads keep
    their deterministic routes. When ``control_focus_ai_read_fallback_enabled`` is
    true, unresolved read-only home questions may use the bounded AI Evidence Planner;
    control candidates and automation writes remain excluded by that planner's safety
    matcher. Disabling the option restores the fully locked-down Control Focus scope.

    ``activate_runtime=False`` is intended for side-effect-free domain validation
    in regression tests; production entrypoint installation uses the default.
    """

    existing = tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))
    merged = tuple(dict.fromkeys((*existing, *_EXTRA_HOME_DOMAIN_TERMS)))
    planner_module._HOME_DOMAIN_TERMS = merged
    if not activate_runtime:
        return merged

    import app as application

    control_focus_enabled = application.option_bool("control_focus_mode_enabled", True)
    if control_focus_enabled:
        ai_read_fallback = application.option_bool(
            "control_focus_ai_read_fallback_enabled",
            True,
        ) and application.option_bool("ai_evidence_planner_enabled", True)
        planner_module.is_ai_evidence_query = (
            _ORIGINAL_AI_EVIDENCE_QUERY if ai_read_fallback else (lambda _query: False)
        )
        install_control_focus_power_summary_safe()
        install_control_focus_ai_fallback_scope()
        metric_executor = SemanticMetricComparisonExecutor(application.fallback)
        service = install_control_focus_mode(
            application,
            metric_executor,
            enabled=True,
            allow_verified_reads=application.option_bool(
                "control_focus_allow_verified_reads",
                True,
            ),
        )
        service.ai_read_fallback_enabled = ai_read_fallback
        install_control_focus_octopus_energy(application)
    else:
        planner_module.is_ai_evidence_query = _ORIGINAL_AI_EVIDENCE_QUERY
    return merged


def installed_domain_terms() -> tuple[str, ...]:
    return tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))


__all__ = [
    "install_ai_evidence_domains",
    "installed_domain_terms",
]
