"""Tests for backend/agents/orchestrator_agent.py — _post_validate_decision."""
import pytest
from unittest.mock import patch
from tests.conftest import make_state, make_routing_decision


@pytest.fixture(autouse=True)
def patch_llm_and_settings():
    with patch("backend.agents.orchestrator_agent.AzureChatOpenAI"), \
         patch("backend.agents.orchestrator_agent.settings"):
        yield


from backend.agents.orchestrator_agent import _post_validate_decision  # noqa: E402


# ---------------------------------------------------------------------------
# process_invoice routing
# ---------------------------------------------------------------------------

class TestProcessInvoiceRouting:

    def test_routes_to_invoice_agent_when_state_has_path(self):
        state = make_state(invoice_file_path="/app/uploads/abc.pdf")
        decision = make_routing_decision(intent="process_invoice")
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "process_invoice"
        assert result["selected_agent"] == "invoice_agent"
        assert result["missing_fields"] == []

    def test_ask_followup_when_no_file_in_state(self):
        state = make_state(invoice_file_path=None)
        decision = make_routing_decision(intent="process_invoice", invoice_file_path="invoice.pdf")
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "ask_followup"
        assert result["selected_agent"] is None
        assert "invoice_file_path" in result["missing_fields"]

    def test_llm_filename_never_used(self):
        """LLM-extracted filename must not leak into the returned state."""
        state = make_state(invoice_file_path=None)
        decision = make_routing_decision(intent="process_invoice", invoice_file_path="fake.pdf")
        result = _post_validate_decision(state, decision)
        assert result["invoice_file_path"] is None

    def test_server_path_preserved_unchanged(self):
        path = "/app/uploads/f9f8-real.pdf"
        state = make_state(invoice_file_path=path)
        decision = make_routing_decision(intent="process_invoice", invoice_file_path="invoice.pdf")
        result = _post_validate_decision(state, decision)
        assert result["invoice_file_path"] == path

    def test_empty_string_path_triggers_followup(self):
        state = make_state(invoice_file_path="")
        decision = make_routing_decision(intent="process_invoice")
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "ask_followup"


# ---------------------------------------------------------------------------
# search_hotels routing
# ---------------------------------------------------------------------------

class TestSearchHotelsRouting:

    def test_routes_when_location_in_decision(self):
        state = make_state()
        decision = make_routing_decision(intent="search_hotels", location="London")
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "search_hotels"
        assert result["selected_agent"] == "search_availability_agent"

    def test_routes_when_location_in_state(self):
        state = make_state(location="Paris")
        decision = make_routing_decision(intent="search_hotels", location=None)
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "search_hotels"

    def test_ask_followup_when_no_location(self):
        state = make_state()
        decision = make_routing_decision(intent="search_hotels", location=None)
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "ask_followup"
        assert "location" in result["missing_fields"]


# ---------------------------------------------------------------------------
# check_availability routing
# ---------------------------------------------------------------------------

class TestCheckAvailabilityRouting:

    def test_routes_when_all_fields_present(self):
        state = make_state(hotel_id=1, check_in="2026-05-01", check_out="2026-05-05", guests=2)
        decision = make_routing_decision(
            intent="check_availability",
            hotel_id=1, check_in="2026-05-01", check_out="2026-05-05", guests=2
        )
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "check_availability"
        assert result["selected_agent"] == "search_availability_agent"

    def test_ask_followup_missing_hotel_id(self):
        state = make_state(check_in="2026-05-01", check_out="2026-05-05", guests=2)
        decision = make_routing_decision(
            intent="check_availability",
            check_in="2026-05-01", check_out="2026-05-05", guests=2
        )
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "ask_followup"
        assert "hotel_id" in result["missing_fields"]

    def test_ask_followup_missing_dates(self):
        state = make_state(hotel_id=1, guests=2)
        decision = make_routing_decision(intent="check_availability", hotel_id=1, guests=2)
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "ask_followup"
        assert "check_in" in result["missing_fields"]
        assert "check_out" in result["missing_fields"]


# ---------------------------------------------------------------------------
# create_booking routing
# ---------------------------------------------------------------------------

class TestCreateBookingRouting:

    def test_ask_followup_missing_user_fields(self):
        state = make_state(
            hotel_id=1, check_in="2026-05-01", check_out="2026-05-05",
            guests=2, room_type="Standard"
        )
        decision = make_routing_decision(
            intent="create_booking",
            hotel_id=1, check_in="2026-05-01", check_out="2026-05-05",
            guests=2, room_type="Standard"
        )
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "ask_followup"
        assert "user_name" in result["missing_fields"]
        assert "user_email" in result["missing_fields"]

    def test_routes_when_all_fields_present(self):
        state = make_state(
            hotel_id=1, check_in="2026-05-01", check_out="2026-05-05",
            guests=2, room_type="Standard",
            user_name="Alice", user_email="alice@example.com"
        )
        decision = make_routing_decision(
            intent="create_booking",
            hotel_id=1, check_in="2026-05-01", check_out="2026-05-05",
            guests=2, room_type="Standard"
        )
        result = _post_validate_decision(state, decision)
        assert result["intent"] == "create_booking"
        assert result["selected_agent"] == "booking_agent"


# ---------------------------------------------------------------------------
# confirm_booking routing
# ---------------------------------------------------------------------------

class TestConfirmBookingRouting:

    def test_routes_to_booking_agent(self):
        state = make_state()
        decision = make_routing_decision(intent="confirm_booking")
        result = _post_validate_decision(state, decision)
        assert result["selected_agent"] == "booking_agent"


# ---------------------------------------------------------------------------
# reject_request / ask_followup routing
# ---------------------------------------------------------------------------

class TestFallbackRouting:

    def test_reject_request_has_no_agent(self):
        state = make_state()
        decision = make_routing_decision(intent="reject_request")
        result = _post_validate_decision(state, decision)
        assert result["selected_agent"] is None

    def test_ask_followup_has_no_agent(self):
        state = make_state()
        decision = make_routing_decision(intent="ask_followup")
        result = _post_validate_decision(state, decision)
        assert result["selected_agent"] is None


# ---------------------------------------------------------------------------
# State field merging
# ---------------------------------------------------------------------------

class TestStateFieldMerging:

    def test_decision_location_preferred_over_state(self):
        state = make_state(location="OldCity")
        decision = make_routing_decision(intent="search_hotels", location="NewCity")
        result = _post_validate_decision(state, decision)
        assert result["location"] == "NewCity"

    def test_state_location_used_as_fallback(self):
        state = make_state(location="FallbackCity")
        decision = make_routing_decision(intent="search_hotels", location=None)
        result = _post_validate_decision(state, decision)
        assert result["location"] == "FallbackCity"
