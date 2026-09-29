from performance_semantic_grounding import ground_performance_semantics


def test_likely_primary_source_localization_keeps_metric_without_dangling_relation():
    draft = "LG webOS TV averaged 3,073ms and is likely the primary source of hub stutter."
    corrected = ground_performance_semantics(draft)
    assert "3,073ms" in corrected
    assert "is likely the;" not in corrected
    assert "and;" not in corrected
    assert corrected.startswith("LG webOS TV averaged 3,073ms;")
    assert "current statistics do not establish" in corrected


def test_outcome_localization_does_not_preserve_unmeasured_prefix_as_measured_fact():
    draft = "LG webOS TV is likely the primary source of hub stutter."
    corrected = ground_performance_semantics(draft)
    assert not corrected.startswith("LG webOS TV;")
    assert corrected.startswith("This is a measured performance concern")
