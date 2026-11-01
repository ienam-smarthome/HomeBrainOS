"""Stage 9.4: independent causal status may not contradict model certainty.

These fixtures use only synthetic read-only evidence; no Hubitat, HA, or
Ollama requests occur.
"""
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from causal_answer_coverage_alignment import (
    align_causal_answer_with_coverage, unresolved_causal_hypotheses,
)


def unresolved_coverage():
    return {
        "domain": "causal_provenance",
        "status": "source-checks-complete",
        "sourceChecksComplete": True,
        "rootCauseVerified": None,
        "questionResolved": None,
        "hypothesisComparisonStatus": "model-proposed-source-checks-not-causal-verdicts",
        "hypothesisComparisons": [
            {"candidate": "Synthetic timed automation",
             "source_state": "source-class-checked-verdict-unverified",
             "discriminator_verified": False,
             "hypothesis_verdict": "unverified"},
            {"candidate": "Synthetic scheduled command",
             "source_state": "source-class-checked-verdict-unverified",
             "discriminator_verified": False,
             "hypothesis_verdict": "unverified"},
        ],
    }


def test_stage94_downgrades_model_certainty_but_preserves_issuer_and_timeline():
    source = (
        "The investigation into the OFF command issued by app 4012 is complete based on current evidence.\n"
        "### Conclusion\n"
        "**Leading Explanation:** The OFF command was issued by the **Inactive Motion Timeout** logic within app 4012.\n"
        "**Confidence:** High (Direct provenance and verified source implementation).\n"
        "15:29:23.157 UTC: app 4012 recorded off().\n"
        "The actual motion event was not retrieved.\n"
    )
    corrected, changed = align_causal_answer_with_coverage(source, unresolved_coverage())
    assert changed
    assert corrected.startswith("**Causal verification status: Unverified.**")
    assert "**Leading hypothesis (unverified):**" in corrected
    assert "could have arisen from the **Inactive Motion Timeout** logic" in corrected
    assert "**Root-cause confidence:** Unverified" in corrected
    assert "**Confidence:** High" not in corrected
    assert "investigation into the OFF command issued by app 4012 is complete" not in corrected
    assert "15:29:23.157 UTC: app 4012 recorded off()." in corrected
    assert "The actual motion event was not retrieved." in corrected
    # Idempotent across retries/serialization: never stack banners.
    again, changed_again = align_causal_answer_with_coverage(corrected, unresolved_coverage())
    assert not changed_again
    assert again == corrected


def test_stage94_proven_root_cause_must_not_be_downgraded():
    status = unresolved_coverage()
    status["rootCauseVerified"] = True
    source = "**Confidence:** High.\n**Leading Explanation:** Proven sensor action."
    assert not unresolved_causal_hypotheses(status)
    assert align_causal_answer_with_coverage(source, status) == (source, False)


def test_stage94_checked_sources_alone_never_verify_hypothesis():
    status = unresolved_coverage()
    assert unresolved_causal_hypotheses(status)
    status["hypothesisComparisons"][0]["source_state"] = "source-class-checked-verdict-unverified"
    assert unresolved_causal_hypotheses(status)
    status["hypothesisComparisons"][0]["discriminator_verified"] = True
    assert not unresolved_causal_hypotheses(status)


def test_stage94_no_hypothesis_provenance_means_no_confidence_rewrite():
    source = "**Confidence:** High for a separate fact, unrelated to cause."
    for coverage in (None, {}, {"hypothesisComparisons": []}, {"rootCauseVerified": False}):
        assert align_causal_answer_with_coverage(source, coverage) == (source, False)


def test_stage94_cautious_answer_remains_natural_language_without_extra_banner():
    source = (
        "The recorded OFF command identifies the producing app. "
        "A motion timeout is plausible, but sensor history is missing."
    )
    assert align_causal_answer_with_coverage(source, unresolved_coverage()) == (source, False)


def test_stage94_orchestrator_gates_message_after_hypothesis_comparisons():
    orchestrator = (APP / "mcp_agent_orchestrator.py").read_text()
    alignment = orchestrator.index("message, confidence_aligned = align_causal_answer_with_coverage(")
    comparison = orchestrator.index('"hypothesisComparisons": comparisons,')
    publication = orchestrator.index("return AgentOutcome(\n                message=message,")
    assert comparison < alignment < publication
    assert "causal_coverage_confidence_aligned" in orchestrator
