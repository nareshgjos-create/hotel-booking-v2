"""Tests for backend/agents/booking_agent.py"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import backend.agents.booking_agent as booking_module
from backend.agents.booking_agent import _extract_transaction_id, run_booking_agent


def _ai(content="ok"):
    r = MagicMock(spec=AIMessage)
    r.content = content
    r.tool_calls = []
    return r


class TestExtractTransactionId:

    def test_finds_txn_in_tool_message(self):
        msgs = [ToolMessage(content="Payment approved TXN-ABCDEF012345", tool_call_id="1")]
        assert _extract_transaction_id(msgs) == "TXN-ABCDEF012345"

    def test_finds_txn_in_ai_message(self):
        msgs = [AIMessage(content="Your transaction is TXN-123456ABCDEF")]
        assert _extract_transaction_id(msgs) == "TXN-123456ABCDEF"

    def test_returns_na_when_not_found(self):
        msgs = [HumanMessage(content="no transaction here")]
        assert _extract_transaction_id(msgs) == "N/A"

    def test_picks_most_recent(self):
        msgs = [
            ToolMessage(content="TXN-AAAAAA000000", tool_call_id="1"),
            ToolMessage(content="TXN-BBBBBB111111", tool_call_id="2"),
        ]
        assert _extract_transaction_id(msgs) == "TXN-BBBBBB111111"

    def test_empty_messages(self):
        assert _extract_transaction_id([]) == "N/A"


class TestRunBookingAgentSteps:
    """
    Patch the module-level LLM variables directly, since they are created
    at import time and cannot be intercepted by patching the class constructor.
    """

    def _state(self, booking_step, msgs=None):
        return {
            "messages": msgs or [HumanMessage(content="ok")],
            "booking_step": booking_step,
            "user_name": "Alice",
            "user_email": "alice@example.com",
        }

    def test_step1_price_calculation(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _ai()
        with patch.object(booking_module, "_price_llm", mock_llm), \
             patch.object(booking_module, "langfuse_context"), \
             patch.object(booking_module, "logger"):
            result = run_booking_agent(self._state(""))
        assert result["booking_step"] == "price_shown"
        mock_llm.invoke.assert_called_once()

    def test_step2_show_price(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _ai("Here is your price...")
        with patch.object(booking_module, "_chat_llm", mock_llm), \
             patch.object(booking_module, "langfuse_context"), \
             patch.object(booking_module, "logger"):
            result = run_booking_agent(self._state("price_shown"))
        assert result["booking_step"] == "awaiting_payment"

    def test_step3_process_payment(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _ai()
        with patch.object(booking_module, "_process_pay_llm", mock_llm), \
             patch.object(booking_module, "langfuse_context"), \
             patch.object(booking_module, "logger"):
            result = run_booking_agent(self._state(
                "awaiting_payment",
                msgs=[HumanMessage(content="4111111111111111 Alice")]
            ))
        assert result["booking_step"] == "payment_done"

    def test_step4_create_booking(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _ai()
        with patch.object(booking_module, "_create_booking_llm", mock_llm), \
             patch.object(booking_module, "langfuse_context"), \
             patch.object(booking_module, "logger"):
            result = run_booking_agent(self._state(
                "payment_done",
                msgs=[ToolMessage(content="TXN-ABCDEF012345 approved", tool_call_id="1")]
            ))
        assert result["booking_step"] == "done"

    def test_step5_confirmation(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _ai("Booking confirmed!")
        with patch.object(booking_module, "_chat_llm", mock_llm), \
             patch.object(booking_module, "langfuse_context"), \
             patch.object(booking_module, "logger"):
            result = run_booking_agent(self._state(
                "done",
                msgs=[ToolMessage(content="booking created", tool_call_id="1")]
            ))
        assert result["booking_step"] == ""

    def test_unknown_step_resets(self):
        with patch.object(booking_module, "langfuse_context"), \
             patch.object(booking_module, "logger"):
            result = run_booking_agent(self._state("unknown_step"))
        assert result["booking_step"] == ""
        assert result["messages"] == []
