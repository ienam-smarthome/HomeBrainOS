from agent_prompt_policy import build_system_prompt


def test_broad_performance_prompt_requires_bounded_diagnostic_breadth():
    prompt = build_system_prompt("Device manifest omitted or unavailable.")
    assert "bounded recent log window" in prompt
    assert "limit': 100" in prompt
    assert "scheduler/job evidence" in prompt
    assert "last-activity/history evidence" in prompt
    assert "databaseSizeMB" in prompt
    assert "explicit numeric database size in MB" in prompt
    assert "measured findings, recent observed patterns, hypotheses, and grounded next actions" in prompt
