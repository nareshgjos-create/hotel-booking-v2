"""Tests for backend/guardrails/output_guardrail.py"""
import pytest
from backend.guardrails.output_guardrail import sanitize_output, sanitize_error_message


class TestSanitizeOutput:
    def test_none_returns_fallback(self):
        result = sanitize_output(None)
        assert "couldn't generate" in result.lower()

    def test_empty_string_returns_fallback(self):
        result = sanitize_output("")
        assert "couldn't generate" in result.lower()

    def test_whitespace_only_returns_fallback(self):
        result = sanitize_output("   ")
        assert "couldn't generate" in result.lower()

    def test_normal_reply_passed_through(self):
        reply = "Here are hotels in London..."
        assert sanitize_output(reply) == reply

    def test_traceback_blocked(self):
        result = sanitize_output("Traceback (most recent call last): ...")
        assert "went wrong" in result.lower()

    def test_api_key_blocked(self):
        result = sanitize_output("Your api_key is sk-abc123")
        assert "went wrong" in result.lower()

    def test_system_prompt_blocked(self):
        result = sanitize_output("The system prompt says you are an AI...")
        assert "went wrong" in result.lower()

    def test_sqlalchemy_error_blocked(self):
        result = sanitize_output("sqlalchemy.exc.OperationalError: ...")
        assert "went wrong" in result.lower()

    def test_langgraph_reference_blocked(self):
        result = sanitize_output("langgraph node failed with error")
        assert "went wrong" in result.lower()

    def test_tool_calls_blocked(self):
        result = sanitize_output("tool_calls=[{'name': 'search_hotels'}]")
        assert "went wrong" in result.lower()

    def test_long_response_truncated(self):
        long_reply = "a" * 5000
        result = sanitize_output(long_reply)
        assert len(result) <= 4030  # 4000 chars + newlines + "[response truncated]"
        assert "truncated" in result

    def test_exactly_4000_not_truncated(self):
        reply = "a" * 4000
        result = sanitize_output(reply)
        assert "truncated" not in result
        assert len(result) == 4000

    def test_case_insensitive_blocking(self):
        result = sanitize_output("TRACEBACK from the server")
        assert "went wrong" in result.lower()


class TestSanitizeErrorMessage:
    def test_always_returns_generic_message(self):
        result = sanitize_error_message(ValueError("secret db password"))
        assert "went wrong" in result.lower()
        assert "secret" not in result
        assert "password" not in result

    def test_returns_string(self):
        result = sanitize_error_message(Exception("boom"))
        assert isinstance(result, str)
