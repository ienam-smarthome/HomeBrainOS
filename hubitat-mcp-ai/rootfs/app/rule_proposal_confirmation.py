"""Resolves a handled rule-authoring proposal into a response message.

Extracted from `mcp_agent_orchestrator.UnifiedMCPAgent._process_user_request`.
`RuleAuthoringService.propose()` may fully handle a request itself (an
error, or a read-only answer with no write to confirm) or hand back a set
of proposed `hub_manage_rule_machine` actions that need to go through the
normal sensitive-action confirmation flow. This module owns only the second
case: evaluating the confirmation policy for those actions and queuing them.

The caller still owns deciding *whether* to hand a decision here --
`decision.handled` must already be `True` before calling `resolve()`.
"""

from __future__ import annotations

from contextvars import ContextVar

from confirmation_policy import ConfirmationAction, ConfirmationPolicy
from confirmation_store import ConfirmationStore
from rule_authoring_service import RuleAuthoringDecision


class RuleProposalConfirmation:
    """Owns confirmation handling for one handled rule-authoring proposal."""

    def __init__(
        self,
        confirmation_policy: ConfirmationPolicy,
        confirmations: ConfirmationStore,
        mutation_call_seen: ContextVar[bool],
    ) -> None:
        self._confirmation_policy = confirmation_policy
        self._confirmations = confirmations
        self._mutation_call_seen = mutation_call_seen

    def resolve(
        self,
        decision: RuleAuthoringDecision,
        *,
        user_prompt: str,
        session_id: str,
    ) -> str:
        """Return the response message for a handled rule-authoring decision."""

        if decision.message is not None:
            return decision.message

        sensitive = [
            ("hub_manage_rule_machine", dict(arguments))
            for arguments in decision.actions
        ]
        self._mutation_call_seen.set(bool(sensitive))
        policy_decision = self._confirmation_policy.decide(session_id, sensitive)
        if policy_decision.action is ConfirmationAction.REJECT:
            return str(policy_decision.message)

        assistant_message = {
            "role": "assistant",
            "content": str(policy_decision.message),
            "tool_calls": [
                {"function": {"name": name, "arguments": arguments}}
                for name, arguments in sensitive
            ],
        }
        self._confirmations.queue(
            session_id,
            sensitive,
            [{"role": "user", "content": str(user_prompt).strip()}],
            assistant_message,
        )
        return str(policy_decision.message)


__all__ = ["RuleProposalConfirmation"]
