from agent_prompt_policy import build_system_prompt


def test_broad_performance_recommendations_must_read_bounded_logs_before_finalizing():
    prompt = build_system_prompt("Device manifest omitted or unavailable.")
    assert "you MUST read one bounded recent log window" in prompt
    assert "tool='hub_get_logs'" in prompt
    assert "{'since': '30m', 'limit': 100}" in prompt
    assert "Do not finalize a broad performance+recommendations answer" in prompt


def test_performance_prompt_guards_scheduler_hypothesis_database_and_backup_claims():
    prompt = build_system_prompt("Device manifest omitted or unavailable.")
    assert "scheduler/job list" in prompt
    assert "does not by itself prove CPU load" in prompt
    assert "sessionTick interval" in prompt
    assert "A HYPOTHESIS label does not make assertive wording" in prompt
    assert "do not call the database small, lean, large, or bloated" in prompt
    assert "do not call it the most urgent issue" in prompt
    assert "claim imminent data loss" in prompt
