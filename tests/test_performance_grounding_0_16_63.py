from performance_semantic_grounding import ground_performance_semantics


def test_ordered_recommendation_preserves_number_and_title_when_grounded():
    draft = """### Recommended Improvements
1. **Audit LG latency:** Check polling intervals and increase them.
2) **Trim state:** Check app settings to reduce cached data or history stored within the app.
"""
    corrected = ground_performance_semantics(draft)
    assert "1. **Audit LG latency:** Inspect the cited integration/device configuration first." in corrected
    assert "2) **Trim state:** Inspect the cited app implementation/configuration first." in corrected


def test_event_volume_does_not_claim_material_overhead_without_evidence():
    draft = (
        "While its average execution time is low (4.59ms), this volume of events can create "
        "unnecessary hub overhead."
    )
    corrected = ground_performance_semantics(draft)
    assert "Average execution time is 4.59ms." in corrected
    assert "do not establish that it creates material hub overhead" in corrected
    assert "can create unnecessary hub overhead" not in corrected


def test_state_size_storage_inference_is_localized():
    draft = (
        "The large state sizes in Google Calendar, Octopus Energy, and Life360 suggest they are "
        "storing significant amounts of data in the hub's memory."
    )
    corrected = ground_performance_semantics(draft)
    assert "measured state size is worth inspecting" in corrected
    assert "do not establish what data is stored" in corrected


def test_state_cache_recommendation_requires_configuration_evidence():
    draft = (
        "### Recommended Improvements
"
        "3. **Optimize App State:** Check the app settings to see if you can reduce the amount "
        "of cached data or history stored within the app itself.
"
    )
    corrected = ground_performance_semantics(draft)
    assert "3. **Optimize App State:** Inspect the cited app implementation/configuration first." in corrected
    assert "whether cache/history retention is configurable" in corrected
