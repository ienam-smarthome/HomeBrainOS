from performance_live_semantic_guard import guard_live_performance_semantics
from synthesis_validator import validate_synthesis


def _performance_and_log_evidence():
    return [
        {
            "success": True,
            "sub_tool": "hub_get_performance_stats",
            "evidence_kind": "tool_result",
        },
        {
            "success": True,
            "sub_tool": "hub_get_logs",
            "evidence_kind": "tool_result",
            "details": {"logs": []},
        },
    ]


def test_hypothesis_label_does_not_allow_likely_causal_mechanism():
    draft = (
        "*Hypothesis:* This is likely caused by the driver attempting to communicate "
        "with a TV that is asleep or unreachable, causing the thread to hang until a timeout occurs."
    )
    corrected, changed = guard_live_performance_semantics(
        draft, _performance_and_log_evidence()
    )
    assert changed is True
    assert "Possible hypothesis" in corrected
    assert "does not establish which mechanism is responsible" in corrected
    assert "likely caused by" not in corrected


def test_scheduler_job_list_does_not_become_cpu_load_causality():
    draft = (
        "These recurring tasks increase the baseline CPU load."
        " The sessionTick jobs are numerous."
    )
    corrected, changed = guard_live_performance_semantics(
        draft, _performance_and_log_evidence()
    )
    assert changed is True
    assert "does not establish material CPU load" in corrected
    assert "increase the baseline CPU load" not in corrected


def test_sessiontick_interval_tuning_is_inspection_first_without_configuration():
    draft = (
        'Review the app managing the "Block [Device]" jobs. If possible, increase '
        "the sessionTick interval to reduce the total number of scheduled jobs."
    )
    corrected, changed = guard_live_performance_semantics(
        draft, _performance_and_log_evidence()
    )
    assert changed is True
    assert "Inspect the cited scheduler/app configuration first" in corrected
    assert "increase the sessionTick interval" not in corrected


def test_database_mb_is_preserved_without_small_or_performance_drag_inference():
    draft = (
        "Database: Lean. At 166MB, your database is small and unlikely to be causing "
        "any performance drag."
    )
    corrected, changed = guard_live_performance_semantics(
        draft, _performance_and_log_evidence()
    )
    assert changed is True
    assert "166 MB" in corrected
    assert "does not establish a normal-size threshold" in corrected
    assert "database is small" not in corrected
    assert "unlikely to be causing any performance drag" not in corrected


def test_network_backup_alert_does_not_imply_imminent_data_loss():
    draft = (
        "Resolve the `NETWORK_BACKUP_FAILED` alert immediately to prevent data loss."
    )
    corrected, changed = guard_live_performance_semantics(
        draft, _performance_and_log_evidence()
    )
    assert changed is True
    assert "does not establish imminent data loss" in corrected
    assert "immediately to prevent data loss" not in corrected


def test_synthesis_validator_reports_live_performance_semantic_issue():
    draft = "These sessionTick recurring tasks increase the baseline CPU load."
    corrected, issues = validate_synthesis(
        draft,
        _performance_and_log_evidence(),
    )
    assert "performance_live_semantics" in issues
    assert "does not establish material CPU load" in corrected
