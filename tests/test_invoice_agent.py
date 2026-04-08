"""Tests for backend/agents/invoice_agent.py"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture(autouse=True)
def patch_invoice_deps():
    with patch("backend.agents.invoice_agent.AzureChatOpenAI"), \
         patch("backend.agents.invoice_agent.settings"), \
         patch("backend.agents.invoice_agent.logger"):
        yield


from backend.agents.invoice_agent import run_invoice_agent  # noqa: E402


class TestRunInvoiceAgent:

    def test_returns_messages_unchanged_when_no_file_path(self):
        msgs = [HumanMessage(content="process invoice")]
        state = {"messages": msgs, "invoice_file_path": ""}
        result = run_invoice_agent(state)
        # No file → returns original messages unchanged
        assert result["messages"] == msgs

    def test_returns_messages_unchanged_when_path_is_none(self):
        msgs = [HumanMessage(content="process invoice")]
        state = {"messages": msgs, "invoice_file_path": None}
        result = run_invoice_agent(state)
        assert result["messages"] == msgs

    def test_invokes_graph_when_path_present(self):
        ai_response = AIMessage(content="Invoice processed successfully.")
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"messages": [ai_response]}

        with patch("backend.agents.invoice_agent._invoice_graph", mock_graph):
            state = {
                "messages": [HumanMessage(content="process this invoice")],
                "invoice_file_path": "/app/uploads/abc.pdf",
            }
            result = run_invoice_agent(state)

        mock_graph.invoke.assert_called_once()
        call_arg = mock_graph.invoke.call_args[0][0]
        # The agent should pass the file path in the human message content
        assert "/app/uploads/abc.pdf" in call_arg["messages"][0].content
        assert result["messages"] == [ai_response]
