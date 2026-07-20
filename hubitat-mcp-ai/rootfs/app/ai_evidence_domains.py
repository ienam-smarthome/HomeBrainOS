from __future__ import annotations

from typing import Any

import ai_evidence_planner as planner_module
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
    "octopus",
    "meter",
    "tariff",
    "cost",
    "consumption",
)
_ORIGINAL_AI_EVIDENCE_QUERY = planner_module.is_ai_evidence_query


def install_ai_evidence_domains(*, activate_runtime: bool = True) -> tuple[str, ...]:
    """Install broad evidence domains and keep Control Focus as an opt-in restriction.

    Hybrid Assistant mode takes precedence over the legacy Focus option. This matters
    for upgrades because Home Assistant preserves saved add-on options: a previously
    saved ``control_focus_mode_enabled: true`` must not keep blocking AI after the new
    hybrid mode has been enabled.

    ``activate_runtime=False`` is intended for side-effect-free domain validation
    in regression tests; production entrypoint installation uses the default.
    """

    existing = tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))
    merged = tuple(dict.fromkeys((*existing, *_EXTRA_HOME_DOMAIN_TERMS)))
    planner_module._HOME_DOMAIN_TERMS = merged
    if not activate_runtime:
        return merged

    import app as application

    hybrid_enabled = application.option_bool("hybrid_assistant_mode_enabled", True)
    legacy_focus_enabled = application.option_bool("control_focus_mode_enabled", False)
    restricted_focus_enabled = bool(legacy_focus_enabled and not hybrid_enabled)

    if restricted_focus_enabled:
        planner_module.is_ai_evidence_query = lambda _query: False
        install_control_focus_power_summary_safe()
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
