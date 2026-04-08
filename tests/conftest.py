"""
Shared fixtures for the hotel booking test suite.

IMPORTANT: The database module raises at import time if DATABASE_URL is unset,
and creates a real SQLAlchemy engine. We stub it in sys.modules here, before
any backend module is collected, so no DB connection is ever attempted.
"""
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub out the database layer before any backend module is imported
# ---------------------------------------------------------------------------

_db_mock = MagicMock()
_db_mock.SessionLocal = MagicMock()
_db_mock.Base = MagicMock()
_db_mock.engine = MagicMock()
_db_mock.get_db = MagicMock()

_models_mock = MagicMock()
_models_mock.PaymentRecord = MagicMock()
_models_mock.CompanyContact = MagicMock()
_models_mock.Hotel = MagicMock()
_models_mock.RoomType = MagicMock()
_models_mock.Booking = MagicMock()

sys.modules.setdefault("backend.db.database", _db_mock)
sys.modules.setdefault("backend.db.models", _models_mock)
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.extras", MagicMock())


# ---------------------------------------------------------------------------
# Helpers to build a minimal RoutingDecision mock and state dict
# ---------------------------------------------------------------------------

def make_state(**overrides):
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
    base.update(overrides)
    return base


def make_routing_decision(intent="search_hotels", **kwargs):
    d = MagicMock()
    d.intent = intent
    d.invoice_file_path = kwargs.get("invoice_file_path")
    d.location = kwargs.get("location")
    d.hotel_id = kwargs.get("hotel_id")
    d.check_in = kwargs.get("check_in")
    d.check_out = kwargs.get("check_out")
    d.guests = kwargs.get("guests")
    d.room_type = kwargs.get("room_type")
    d.missing_fields = kwargs.get("missing_fields", [])
    return d


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


@pytest.fixture()
def empty_state():
    return make_state()


@pytest.fixture()
def state_with_invoice():
    return make_state(invoice_file_path="/app/uploads/abc-123.pdf")


@pytest.fixture()
def full_booking_state():
    return make_state(
        hotel_id=1,
        check_in="2026-05-01",
        check_out="2026-05-05",
        guests=2,
        room_type="Standard",
        user_name="Alice",
        user_email="alice@example.com",
    )
