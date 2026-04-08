"""
Tests for invoice routing logic in _post_validate_decision and build_followup_question.
No external services or LLM calls are made — all dependencies are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to build a minimal RoutingDecision mock
# ---------------------------------------------------------------------------

def make_decision(intent="process_invoice", invoice_file_path=None, **kwargs):
    d = MagicMock()
    d.intent = intent
    d.invoice_file_path = invoice_file_path
    d.location = kwargs.get("location")
    d.hotel_id = kwargs.get("hotel_id")
    d.check_in = kwargs.get("check_in")
    d.check_out = kwargs.get("check_out")
    d.guests = kwargs.get("guests")
    d.room_type = kwargs.get("room_type")
    d.missing_fields = kwargs.get("missing_fields", [])
    return d


def make_state(**kwargs):
    base = {
        "messages": [],
        "user_name": None,
        "user_email": None,
        "location": None,
        "hotel_id": None,
        "check_in": None,
        "check_out": None,
        "guests": None,
        "room_type": None,
        "room_type_id": None,
        "intent": None,
        "selected_agent": None,
        "missing_fields": [],
        "booking_step": "",
        "payment_transaction_id": None,
        "invoice_file_path": None,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Import the function under test (patch LLM construction so no env vars needed)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_llm(monkeypatch):
    """Prevent AzureChatOpenAI from being instantiated during import."""
    with patch("backend.agents.orchestrator_agent.AzureChatOpenAI"), \
         patch("backend.agents.orchestrator_agent.settings"):
        yield


from backend.agents.orchestrator_agent import _post_validate_decision  # noqa: E402
from backend.api.main import build_followup_question  # noqa: E402


# ---------------------------------------------------------------------------
# _post_validate_decision — process_invoice tests
# ---------------------------------------------------------------------------

class TestProcessInvoiceRouting:

    def test_routes_to_invoice_agent_when_state_has_valid_path(self):
        """If the state already holds a server-side path, route directly to invoice_agent."""
        state = make_state(invoice_file_path="/app/uploads/abc123.pdf")
        decision = make_decision(intent="process_invoice", invoice_file_path=None)

        result = _post_validate_decision(state, decision)

        assert result["intent"] == "process_invoice"
        assert result["selected_agent"] == "invoice_agent"
        assert result["missing_fields"] == []

    def test_falls_back_to_ask_followup_when_no_file_uploaded(self):
        """If no file is in state, fall back to ask_followup even if LLM extracted a name."""
        state = make_state(invoice_file_path=None)
        decision = make_decision(intent="process_invoice", invoice_file_path="invoice.pdf")

        result = _post_validate_decision(state, decision)

        assert result["intent"] == "ask_followup"
        assert result["selected_agent"] is None
        assert "invoice_file_path" in result["missing_fields"]

    def test_ignores_llm_extracted_filename(self):
        """LLM-extracted filenames must never reach the invoice agent."""
        state = make_state(invoice_file_path=None)
        decision = make_decision(intent="process_invoice", invoice_file_path="my_invoice.pdf")

        result = _post_validate_decision(state, decision)

        # The hallucinated path must NOT be propagated
        assert result["invoice_file_path"] is None
        assert result["intent"] == "ask_followup"

    def test_preserves_server_path_in_returned_state(self):
        """The real server-side path must be passed through unchanged."""
        server_path = "/app/uploads/f9f8f9a1-69e1-4edd-91ac-d6ecf5a73a5e.pdf"
        state = make_state(invoice_file_path=server_path)
        decision = make_decision(intent="process_invoice", invoice_file_path="invoice.pdf")

        result = _post_validate_decision(state, decision)

        assert result["invoice_file_path"] == server_path

    def test_empty_string_path_treated_as_missing(self):
        """An empty string path (e.g. default value) should also trigger ask_followup."""
        state = make_state(invoice_file_path="")
        decision = make_decision(intent="process_invoice", invoice_file_path="")

        result = _post_validate_decision(state, decision)

        assert result["intent"] == "ask_followup"
        assert "invoice_file_path" in result["missing_fields"]


# ---------------------------------------------------------------------------
# build_followup_question — invoice_file_path label
# ---------------------------------------------------------------------------

class TestBuildFollowupQuestion:

    def test_invoice_missing_field_produces_clear_message(self):
        msg = build_followup_question(["invoice_file_path"])
        assert "upload" in msg.lower() or "sidebar" in msg.lower()
        assert "invoice" in msg.lower()

    def test_empty_missing_fields_returns_generic_message(self):
        msg = build_followup_question([])
        assert msg  # non-empty

    def test_single_field(self):
        msg = build_followup_question(["location"])
        assert "location" in msg

    def test_two_fields(self):
        msg = build_followup_question(["check_in", "check_out"])
        assert "check-in" in msg
        assert "check-out" in msg

    def test_three_or_more_fields(self):
        msg = build_followup_question(["hotel_id", "check_in", "guests"])
        assert "hotel ID" in msg
        assert "check-in date" in msg
        assert "number of guests" in msg
