"""Stage 4L: cloud transport isolation, constructed corpus and Stage 4K binding."""
import json
from pathlib import Path
import sys
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "rootfs" / "app"))

from stage4l_ollama_cloud_trial import (  # noqa: E402
    DIRECT_MODEL, HOST, SCHEMA, MAX_RESPONSE, DirectCloudOllama,
    _NoRedirect, _synthetic_cases, _proposal_schema,
    _to_stage4a_draft, _offline_author, _private_save,
    run_constructed_trial, main,
)
from stage4_narrative_contract import (  # noqa: E402
    build_stage4_evidence_packet, validate_stage4_model_draft,
)
from stage4k_frozen_answer_audit import freeze_stage4k_answer  # noqa: E402


def test_constructed_cases_are_bounded_and_no_real_household_data():
    cases = _synthetic_cases()
    assert [c["domain"] for c in cases] == [
        "lighting", "heating", "ventilation", "history"]
    for case in cases:
        source = build_stage4_evidence_packet(case["receipts"])
        assert source["facts"]
        assert 1 <= len(source["facts"]) <= 8
        assert source["shadow_only"] is True
        assert "192.168" not in json.dumps(case)
    assert DIRECT_MODEL == "gemma4:31b"
    assert HOST == "https://ollama.com/api/chat"


def test_offline_default_author_produces_frozen_stage4k_bundle():
    report, bundles = run_constructed_trial(_offline_author)
    assert report["cases"] == {"attempted": 4, "responses": 4, "typed_valid": 4,
                                "frozen": 4, "failed": 0}
    assert len(bundles) == 4
    for b in bundles:
        packet = build_stage4_evidence_packet(b["receipts"])
        assert validate_stage4_model_draft(b["draft"], packet)["structured_claims_valid"]
        assert freeze_stage4k_answer(b["receipts"], b["draft"]) == b["frozen"]
    assert not report["publication_approval"]
    assert not report["semantic_completeness_proven"]
    assert not report["real_cloud_quality_measured"]


def test_host_witness_does_not_certify_generated_prose():
    case = _synthetic_cases()[1]
    packet = build_stage4_evidence_packet(case["receipts"])
    proposal = _offline_author(packet, case["question"])
    proposal["sections"][0]["sentences"][0]["text"] = (
        "The setpoint command proves the boiler fired and the valves opened.")
    draft = _to_stage4a_draft(proposal, packet)
    assert validate_stage4_model_draft(draft, packet)["structured_claims_valid"]
    assert freeze_stage4k_answer(case["receipts"], draft)
    # This is the exact known Stage 4A/4K limitation: semantically unsafe
    # prose can still carry exact, host-reconstructed typed witnesses.
    report, _ = run_constructed_trial(lambda _p, _q: proposal, case_limit=1)
    assert report["publication_approval"] is False
    assert report["semantic_completeness_proven"] is False


@pytest.mark.parametrize("modifier", [
    lambda p: p.update(schema="wrong"),
    lambda p: p["sections"][0]["sentences"][0].update(fact_ids=["f999"]),
    lambda p: p["sections"][0]["sentences"][0].update(text=""),
    lambda p: p["sections"][0]["sentences"][0].update(other="unsanctioned"),
    lambda p: p["sections"][0]["sentences"][0].update(fact_ids=["f001", "f001"]),
    lambda p: p.update(sections=[]),
])
def test_bad_proposals_fail_without_publishing(modifier):
    packet = build_stage4_evidence_packet(_synthetic_cases()[0]["receipts"])
    proposal = _offline_author(packet, "constructed")
    modifier(proposal)
    with pytest.raises(ValueError):
        _to_stage4a_draft(proposal, packet)


def test_model_error_is_aggregate_only_and_stops_after_one_attempt_per_case():
    calls = []
    def fail(_packet, question):
        calls.append(question)
        raise RuntimeError("TOKEN-DO-NOT-PRINT-OR-SHARE")
    report, bundles = run_constructed_trial(fail, case_limit=2)
    assert report["cases"]["attempted"] == 2
    assert report["cases"]["responses"] == 0
    assert report["cases"]["failed"] == 2
    assert bundles == []
    assert len(calls) == 2
    assert "TOKEN-" not in json.dumps(report)


def test_model_response_containing_private_strings_does_not_enter_aggregate():
    def bad(_p, _q):
        return {"schema": SCHEMA, "sections": [{
            "name": "evidence", "sentences": [{
                "text": "192.168.1.239 secret-data", "fact_ids": ["wrong"]
            }]
        }]}
    report, _ = run_constructed_trial(bad, case_limit=1)
    assert report["cases"]["failed"] == 1
    assert "192.168" not in json.dumps(report)
    assert "secret-data" not in json.dumps(report)


class FakeHTTP:
    def __init__(self, data):
        self.data = data
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, amount):
        return self.data[:amount]


class FakeOpener:
    def __init__(self, answer):
        self.answer = answer
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request, self.timeout = request, timeout
        return FakeHTTP(self.answer)


def test_direct_cloud_protocol_with_fake_network_no_real_inference():
    case = _synthetic_cases()[0]
    packet = build_stage4_evidence_packet(case["receipts"])
    proposal = _offline_author(packet, case["question"])
    outer = {"message": {"content": json.dumps(proposal)}}
    opener = FakeOpener(json.dumps(outer).encode())
    adapter = DirectCloudOllama("a" * 32, opener=opener)
    assert adapter(packet, case["question"]) == proposal
    assert opener.request.full_url == HOST
    assert opener.request.get_header("Authorization") == "Bearer " + "a" * 32
    assert opener.timeout == 120
    body = json.loads(opener.request.data)
    assert body["model"] == DIRECT_MODEL
    assert body["stream"] is False
    assert body["format"] == _proposal_schema(packet)
    assert "reference_atoms" not in json.dumps(body)
    assert "adjudication" not in json.dumps(body)
    assert "a" * 32 not in json.dumps(body)


def test_cloud_transport_rejects_overlong_and_malformed_replies():
    packet = build_stage4_evidence_packet(_synthetic_cases()[0]["receipts"])
    for response in (b"x" * (MAX_RESPONSE + 1), b"invalid-json",
                     b'{"message":{"content":"[]"}}',
                     b'{"message":{}}'):
        adapter = DirectCloudOllama("a" * 32, opener=FakeOpener(response))
        with pytest.raises((ValueError, json.JSONDecodeError)):
            adapter(packet, "constructed")


def test_redirect_and_bad_credentials_denied():
    with pytest.raises(ValueError):
        DirectCloudOllama("")
    with pytest.raises(ValueError, match="redirect"):
        _NoRedirect().redirect_request(None, None, 302, "", {}, HOST)


def test_private_bundle_requires_new_absolute_file_and_mode_0600(tmp_path):
    dest = tmp_path / "private-review.json"
    report, bundles = run_constructed_trial(_offline_author, case_limit=1)
    assert report["cases"]["frozen"] == 1
    _private_save(str(dest), bundles)
    saved = json.loads(dest.read_text())
    assert saved["cases"][0]["frozen"] == bundles[0]["frozen"]
    assert dest.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        _private_save(str(dest), bundles)
    with pytest.raises(ValueError):
        _private_save("relative.json", bundles)


def test_cli_never_calls_cloud_without_three_explicit_opt_ins(monkeypatch, capsys):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert main(["--case-limit", "1"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["cases"]["attempted"] == 1
    assert result["real_cloud_quality_measured"] is False
    with pytest.raises(SystemExit):
        main(["--enable-cloud-inference"])
    with pytest.raises(SystemExit):
        main(["--enable-cloud-inference", "--ack-cloud-billing",
              "--ack-constructed-data-only"])


def test_stage4l_remains_completely_outside_live_runtime_imports():
    for filename in ("app.py", "mcp_agent_orchestrator.py",
                     "final_answer_coordinator.py", "causal_claim_publication.py"):
        content = (ROOT / "rootfs" / "app" / filename).read_text()
        assert "stage4l_ollama_cloud_trial" not in content
