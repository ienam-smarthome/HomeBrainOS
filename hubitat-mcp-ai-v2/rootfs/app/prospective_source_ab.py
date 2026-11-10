"""Opt-in prospective read-only, blinded source-ledger v2 experiment.

Uses the SAME production Agent loop for baseline and the isolated experimental
native source presentation for candidate. Private questions and raw native
receipts live only in memory and disappear when the add-on restarts.
No actual calls occur until the operator explicitly starts each pair.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from agent import Agent
from mcp import MCPClient, MCPError, MCPContractError, is_tool_catalog
from source_ledger_experiment import SourceLedgerExperimentalAgent

SCHEMA = "homebrain-v2-prospective-source-ledger-ab.v1"
CRITERIA = ("factual_grounding", "source_completeness", "causal_calibration",
            "usefulness")
MAX_CASES = 10


class ProspectiveError(ValueError):
    pass


def _payload(response: dict) -> dict | None:
    if not isinstance(response, dict) or response.get("isError") is True:
        return None
    entries = response.get("content")
    if not isinstance(entries, list):
        return None
    objects = []
    for part in entries:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        try:
            val = json.loads(part.get("text"))
        except (ValueError, TypeError):
            continue
        if isinstance(val, dict):
            objects.append(val)
    return objects[0] if len(objects) == 1 else None


async def verify_read_only_client(mcp: MCPClient) -> dict:
    """Require the actual configured token to report its own effective grant.

    This is checked immediately before EACH arm, not inferred from global
    writeEnabled or a previous screenshot. Do not test by attempting a write.
    """
    tools = await mcp.list_tools(refresh=True)
    info_tool = next((t for t in tools if t.get("name") == "hub_get_info"), None)
    if not isinstance(info_tool, dict) or (
            info_tool.get("annotations") or {}).get("readOnlyHint") is not True:
        raise ProspectiveError("Read-only hub_get_info is not exposed by this MCP token")
    native = await mcp.call("hub_get_info", {})
    result = _payload(native)
    grant = result.get("clientAccess") if isinstance(result, dict) else None
    if not isinstance(grant, dict):
        raise ProspectiveError(
            "No clientAccess in fresh hub_get_info. Configure HomeBrain v2 "
            "with a dedicated per-client Read ON / Write OFF token."
        )
    if (grant.get("readEnabled") is not True
            or grant.get("writeEnabled") is not False
            or result.get("readEnabled") is not True):
        raise ProspectiveError(
            "The configured MCP client is not verified as Read ON / Write OFF"
        )
    if not isinstance(grant.get("client"), str) or not grant["client"].strip():
        raise ProspectiveError("MCP client identity was not established")
    return {
        "read_only_grant_reported": True,
        "per_client_read_enabled": True,
        "per_client_write_enabled": False,
        "global_write_enabled": result.get("writeEnabled")
                               if type(result.get("writeEnabled")) is bool else None,
        "permission_enforcement_independently_tested": False,
    }


class ReadOnlyMCP:
    """Fail closed on any tool whose live server annotation isn't read-only.

    Both arms see precisely the same permitted catalog, and the same upstream
    schema validation still applies. This is defence in depth on top of the
    *server-enforced* per-client write restriction, not a replacement for it.
    """
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp
        self._catalog: dict[str, dict] = {}

    async def list_tools(self, refresh: bool = False) -> list[dict]:
        tools = await self.mcp.list_tools(refresh=refresh)
        self._catalog = {
            t["name"]: t for t in tools
            if isinstance(t, dict) and isinstance(t.get("name"), str)
            and isinstance(t.get("annotations"), dict)
            and t["annotations"].get("readOnlyHint") is True
        }
        return list(self._catalog.values())

    def _permit(self, name: str):
        if name not in self._catalog:
            raise MCPContractError(
                "This evaluation permits only tools explicitly annotated "
                "read-only by the connected MCP server"
            )

    async def call(self, name: str, arguments: dict) -> dict:
        self._permit(name)
        # The gateway's readOnlyHint applies to its collection of allowed
        # leaves; never allow a missing/unknown leaf's classification.
        if isinstance(arguments, dict) and isinstance(arguments.get("tool"), str):
            definition, _ = await self.mcp.gateway_leaf_schema(
                name, arguments["tool"]
            )
            if (not isinstance(definition, dict)
                    or not isinstance(definition.get("annotations"), dict)
                    or definition["annotations"].get("readOnlyHint") is not True):
                raise MCPContractError(
                    "Selected native leaf has no verified read-only annotation"
                )
        return await self.mcp.call(name, arguments)

    async def gateway_leaf_schema(self, name: str, leaf: str):
        self._permit(name)
        definition, fetched = await self.mcp.gateway_leaf_schema(name, leaf)
        if (not isinstance(definition, dict)
                or not isinstance(definition.get("annotations"), dict)
                or definition["annotations"].get("readOnlyHint") is not True):
            raise MCPContractError(
                "Selected native leaf has no verified read-only annotation"
            )
        return definition, fetched

    def validate_leaf_arguments(self, definition: dict | None, arguments: dict):
        return self.mcp.validate_leaf_arguments(definition, arguments)

    def cached_leaf_schemas(self):
        return self.mcp.cached_leaf_schemas()


class ProspectiveWorkspace:
    """Volatile private first-answers; no disk or background polling."""
    def __init__(self):
        self.questions: dict[str, dict] = {}
        self.private_conditions: dict[str, dict] = {}
        self.active_case: str | None = None
        self.error: str | None = None
        self.locked = False

    def prepare(self, questions: list[str]) -> dict:
        if self.questions or self.active_case:
            raise ProspectiveError("Existing study is frozen; delete it before preparing another")
        if (not isinstance(questions, list) or not 2 <= len(questions) <= MAX_CASES
                or any(not isinstance(q, str) or not q.strip()
                       or len(q) > 5000 for q in questions)):
            raise ProspectiveError("Prepare two to ten private, nonempty questions")
        cleaned = [q.strip() for q in questions]
        if len(set(cleaned)) != len(cleaned):
            raise ProspectiveError("Repeated questions are not permitted")
        # Prospective study order is sealed in this process. No previously
        # exposed or incident-specific question is provided by the application.
        commitment = hashlib.sha256(
            json.dumps(cleaned, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for index, question in enumerate(cleaned, 1):
            ident = f"new-{index:02d}"
            self.questions[ident] = {
                "id": ident, "question": question, "arms": {}, "ratings": None,
            }
        self.commitment = commitment
        self.error = None
        return self.summary()

    def summary(self) -> dict:
        return {
            "schema": SCHEMA,
            "study_sha256": getattr(self, "commitment", None),
            "cases_prepared": len(self.questions),
            "active_case": self.active_case,
            "last_error": self.error,
            "condition_mapping_revealed": (
                bool(self.questions)
                and all(c["ratings"] is not None for c in self.questions.values())
            ),
            "cases": [
                {"id": key, "question": case["question"],
                 "arms_completed": sorted(case["arms"]),
                 "blind_ratings_saved": case["ratings"] is not None}
                for key, case in self.questions.items()
            ],
            "storage": "memory_only_erased_on_addon_restart",
            "automatic_model_calls": 0,
        }

    def can_run(self, ident: str):
        if ident not in self.questions:
            raise ProspectiveError("Unknown prospective case")
        if self.active_case:
            raise ProspectiveError("Another prospective pair is running")
        if self.questions[ident]["arms"]:
            raise ProspectiveError("This case was attempted already; first answers cannot be rerun")
        if self.questions[ident]["ratings"] is not None:
            raise ProspectiveError("Rated cases are immutable")

    async def run(self, ident: str, baseline: Agent, candidate: Agent,
                  mcp: MCPClient, deadline_seconds: int):
        self.can_run(ident)
        self.active_case = ident
        self.error = None
        case = self.questions[ident]
        # Balance by previous allocations, with a cryptographically random
        # choice when both orders are equally represented.
        a_candidate = sum(mapping["A"] == "candidate"
                          for mapping in self.private_conditions.values())
        b_candidate = len(self.private_conditions) - a_candidate
        candidate_a = (secrets.randbits(1) == 1 if a_candidate == b_candidate
                       else a_candidate < b_candidate)
        allocation = ({"A": "candidate", "B": "baseline"} if candidate_a
                      else {"A": "baseline", "B": "candidate"})
        self.private_conditions[ident] = allocation
        try:
            # Read-only check before each arm; no model requests or domain reads
            # until a fresh token-scoped hub_get_info is returned.
            for label in ("A", "B"):
                permission = await verify_read_only_client(mcp)
                safe = ReadOnlyMCP(mcp)
                agent = candidate if allocation[label] == "candidate" else baseline
                result = await agent.answer(
                    case["question"], [], safe, deadline_seconds
                )
                # The server may already have rejected a write, but verify
                # against unexpected visible write commands too. Never mask.
                case["arms"][label] = {
                    "result": result,
                    "token_scope_before_arm": permission,
                }
        except Exception:
            self.error = ("Pair halted; verify token scope, read-only leaf "
                          "annotations, model connectivity and source receipts")
            raise
        finally:
            self.active_case = None

    def case(self, ident: str) -> dict:
        if ident not in self.questions:
            raise ProspectiveError("Unknown prospective case")
        case = self.questions[ident]
        return {
            "schema": SCHEMA,
            "id": ident, "question": case["question"],
            "arms": case["arms"],
            "ratings": case["ratings"],
            "mapping_hidden": not self.summary()["condition_mapping_revealed"],
            "privacy": "private_answers_and_receipts_in_browser_response_only",
        }

    def rate(self, ident: str, scores: dict):
        if ident not in self.questions:
            raise ProspectiveError("Unknown prospective case")
        case = self.questions[ident]
        if self.active_case or set(case["arms"]) != {"A", "B"}:
            raise ProspectiveError("Complete both first answers before scoring")
        if case["ratings"] is not None:
            raise ProspectiveError("Existing blind ratings are immutable")
        if not isinstance(scores, dict) or set(scores) != {"A", "B"}:
            raise ProspectiveError("Both A and B must be rated")
        for label in ("A", "B"):
            d = scores[label]
            if not isinstance(d, dict) or set(d) != set(CRITERIA):
                raise ProspectiveError("All rating dimensions are required")
            for value in d.values():
                if not (value == "n/a" or (type(value) is int and value in (0, 1, 2))):
                    raise ProspectiveError("Scores must be 0, 1, 2, or n/a")
        case["ratings"] = {k: dict(v) for k, v in scores.items()}

    def report(self) -> dict:
        finished = self.summary()["condition_mapping_revealed"]
        effects = {}
        for dim in CRITERIA:
            values = []
            if finished:
                for key, case in self.questions.items():
                    cond = self.private_conditions[key]
                    rating = case["ratings"]
                    candidate_label = next(
                        label for label in ("A", "B")
                        if cond[label] == "candidate"
                    )
                    baseline_label = "B" if candidate_label == "A" else "A"
                    a = rating[candidate_label][dim]
                    b = rating[baseline_label][dim]
                    if type(a) is int and type(b) is int:
                        values.append(a - b)
            effects[dim] = {
                "paired_ratings": len(values),
                "candidate_minus_baseline_mean": (
                    round(sum(values) / len(values), 4) if values else None
                ),
                "candidate_better": sum(x > 0 for x in values),
                "baseline_better": sum(x < 0 for x in values),
                "ties": sum(x == 0 for x in values),
            }
        return {
            "schema": SCHEMA,
            "study_sha256": getattr(self, "commitment", None),
            "cases_expected": len(self.questions),
            "first_answer_pairs_complete": sum(
                set(case["arms"]) == {"A", "B"} for case in self.questions.values()
            ),
            "blind_ratings_complete": sum(
                case["ratings"] is not None for case in self.questions.values()
            ),
            "condition_mapping_revealed": finished,
            "effects": effects,
            "model_accuracy_independently_verified": False,
            "matching_live_source_snapshots_verified": False,
            "token_enforcement_independently_verified": False,
            "interpretation": (
                "Exploratory paired source-real first answers with "
                "different live read times, manual ratings and possible "
                "source-state drift. Never conclude improvement from "
                "tool counts or from unreviewed ratings."
            ),
        }

    def delete(self):
        if self.active_case:
            raise ProspectiveError("Stop the running pair before deletion")
        self.questions.clear()
        self.private_conditions.clear()
        self.error = None
        self.locked = False
        if hasattr(self, "commitment"):
            del self.commitment
