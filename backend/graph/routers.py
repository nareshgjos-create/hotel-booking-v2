from typing import Literal
from backend.graph.state import HotelAgentState


def route_after_guardrails(
    state: HotelAgentState,
) -> Literal["orchestrator_agent", "reject_node"]:
    """
    Decide where to go after input guardrails.
    """
    policy_decision = state.get("policy_decision", "allow")

    if policy_decision == "block":
        return "reject_node"

    return "orchestrator_agent"


def route_after_orchestrator(
    state: HotelAgentState,
) -> Literal[
    "search_agent",
    "availability_agent",
    "booking_agent",
    "clarification_node",
    "reject_node",
]:
    """
    Decide which specialist node should run next.
    """
    policy_decision = state.get("policy_decision", "allow")
    intent = state.get("intent", "reject_request")

    if policy_decision == "block":
        return "reject_node"

    if policy_decision == "clarify":
        return "clarification_node"

    if intent == "search_hotels":
        return "search_agent"

    if intent == "check_availability":
        return "availability_agent"

    if intent == "create_booking":
        return "booking_agent"

    if intent == "ask_followup":
        return "clarification_node"

    return "reject_node"