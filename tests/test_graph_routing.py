"""Tests for backend/graph/graph.py — routing functions."""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage


# Patch all agent imports before importing graph
@pytest.fixture(autouse=True)
def patch_graph_deps():
    with patch("backend.agents.orchestrator_agent.AzureChatOpenAI"), \
         patch("backend.agents.orchestrator_agent.settings"), \
         patch("backend.agents.booking_agent.AzureChatOpenAI"), \
         patch("backend.agents.booking_agent.settings"), \
         patch("backend.agents.booking_agent.langfuse_context"), \
         patch("backend.agents.booking_agent.logger"), \
         patch("backend.agents.invoice_agent.AzureChatOpenAI"), \
         patch("backend.agents.invoice_agent.settings"), \
         patch("backend.agents.invoice_agent.logger"), \
         patch("backend.agents.search_availability_agent.AzureChatOpenAI"), \
         patch("backend.agents.search_availability_agent.settings"), \
         patch("backend.agents.search_availability_agent.langfuse_context"), \
         patch("backend.agents.search_availability_agent.logger"), \
         patch("backend.graph.graph.logger"):
        yield


from backend.graph.graph import route_after_orchestrator, should_continue_booking, should_continue_search  # noqa: E402


class TestRouteAfterOrchestrator:

    def test_routes_to_search_agent(self):
        state = {"selected_agent": "search_availability_agent", "booking_step": ""}
        assert route_after_orchestrator(state) == "search_availability_agent"

    def test_routes_to_booking_agent(self):
        state = {"selected_agent": "booking_agent", "booking_step": ""}
        assert route_after_orchestrator(state) == "booking_agent"

    def test_routes_to_invoice_agent(self):
        state = {"selected_agent": "invoice_agent", "booking_step": ""}
        assert route_after_orchestrator(state) == "invoice_agent"

    def test_ends_when_no_agent(self):
        from langgraph.graph import END
        state = {"selected_agent": None, "booking_step": ""}
        assert route_after_orchestrator(state) == END

    def test_bypasses_to_booking_when_mid_flow(self):
        for step in ("price_shown", "awaiting_payment", "payment_done", "done"):
            state = {"selected_agent": "search_availability_agent", "booking_step": step}
            assert route_after_orchestrator(state) == "booking_agent", f"Failed for step: {step}"

    def test_does_not_bypass_on_empty_booking_step(self):
        state = {"selected_agent": "search_availability_agent", "booking_step": ""}
        assert route_after_orchestrator(state) == "search_availability_agent"


class TestShouldContinueBooking:

    def test_continues_to_tools_when_tool_calls_present(self):
        msg = MagicMock(spec=AIMessage)
        msg.tool_calls = [{"name": "calculate_price", "args": {}}]
        state = {"messages": [msg]}
        assert should_continue_booking(state) == "tools"

    def test_ends_when_no_tool_calls(self):
        from langgraph.graph import END
        msg = MagicMock(spec=AIMessage)
        msg.tool_calls = []
        state = {"messages": [msg]}
        assert should_continue_booking(state) == END

    def test_ends_when_no_tool_calls_attr(self):
        from langgraph.graph import END
        msg = MagicMock(spec=AIMessage)
        del msg.tool_calls
        state = {"messages": [msg]}
        assert should_continue_booking(state) == END


class TestShouldContinueSearch:

    def test_continues_to_tools_when_tool_calls_present(self):
        msg = MagicMock(spec=AIMessage)
        msg.tool_calls = [{"name": "search_hotels", "args": {}}]
        state = {"messages": [msg]}
        assert should_continue_search(state) == "tools"

    def test_ends_when_no_tool_calls(self):
        from langgraph.graph import END
        msg = MagicMock(spec=AIMessage)
        msg.tool_calls = []
        state = {"messages": [msg]}
        assert should_continue_search(state) == END
