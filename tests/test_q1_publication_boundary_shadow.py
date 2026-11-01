"""Generic, privacy-preserving publication handoff and same-packet prompt tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai" / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

from publication_boundary_shadow import observe_publication_boundary, SCHEMA
from answer_quality_comparison_prompt import render_comparison_prompt
from answer_quality_fixed_packets import build_fixed_packets


def test_observed_replacement_keeps_no_answer_text_or_identifying_details():
    private_draft = (
        "SECRET-HOUSEHOLD-DEVICE is definitely online. "
        "Private command 15:29:23.157 from app 4012."
    )
    private_published = (
        "SECRET-HOUSEHOLD-DEVICE has source-limited state evidence. "
        "Private timestamp 15:29:23.157 is not proof of physical command."
    )
    snapshot = observe_publication_boundary(private_draft, private_published)
    assert snapshot["schema"] == SCHEMA
    assert snapshot["strategy"] == "typed_target_history"
    assert snapshot["replacementPerformed"] is True
    assert snapshot["incomingMessagePresent"] is True
    assert snapshot["incomingVerifiedRawModelDraft"] is False
    assert snapshot["publicationGuardPassed"] is None
    assert snapshot["factualQualityMeasured"] is False
    assert snapshot["containsAnswerText"] is False
    txt = json.dumps(snapshot)
    for secret in ("SECRET", "15:29", "4012", "device", "command"):
        assert secret not in txt.lower() if secret in ("device", "command") else secret not in txt


def test_zero_and_preserved_outcomes_not_confused_with_graded_model():
    empty = observe_publication_boundary("", "")
    assert empty["incomingMessagePresent"] is False
    assert empty["replacementPerformed"] is False
    assert empty["incomingSizeBucket"] == "empty"
    unchanged = observe_publication_boundary("No verified physical state.", "No verified physical state.")
    assert unchanged["replacementPerformed"] is False
    assert unchanged["incomingSizeBucket"] == "1-50"
    assert unchanged["factualQualityMeasured"] is False


def test_unknown_publication_strategy_cannot_echo_arbitrary_text():
    with pytest.raises(ValueError, match="unknown publication strategy"):
        observe_publication_boundary("private data", "more data", strategy="secret-guided")


def test_fixed_prompt_is_deterministic_and_does_not_leak_rubric():
    a = render_comparison_prompt("aq_network_broker_vs_device_health")
    b = render_comparison_prompt("aq_network_broker_vs_device_health")
    assert a == b
    p = next(p for p in build_fixed_packets()
             if p["case_id"] == "aq_network_broker_vs_device_health")
    assert p["packet_sha256"] in a
    assert p["question"] in a
    assert all(item in a for item in p["available_evidence"])
    assert "Do not call MCP" in a
    assert "do not" in a.casefold()
    for secret in ("required_findings", "forbidden_claims", "review_status",
                   "Broker session and endpoint presence are distinct",
                   "Root network/power cause unverified"):
        assert secret not in a


def test_cross_domain_frozen_prompt_has_same_contract():
    packets = build_fixed_packets()
    assert len(packets) == 18
    for packet in packets:
        prompt = render_comparison_prompt(packet["case_id"])
        assert packet["packet_sha256"] in prompt
        assert packet["question"] in prompt
        assert all(item in prompt for item in packet["available_evidence"])
        assert "tool_policy" not in prompt
        assert "required_findings" not in prompt
        assert "forbidden_claims" not in prompt


def test_invalid_packet_id_cannot_construct_a_freeform_remote_prompt():
    with pytest.raises(ValueError, match="Unknown frozen source packet"):
        render_comparison_prompt("fake/device-secret")
