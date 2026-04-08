"""Tests for backend/tools — search, availability, booking, payment, price, invoice, payment status, company contact."""
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path


# ---------------------------------------------------------------------------
# search_hotels
# ---------------------------------------------------------------------------

class TestSearchHotelsTool:

    def test_returns_hotel_list(self):
        hotel = MagicMock()
        hotel.id = 1
        hotel.name = "Grand Hotel"
        hotel.location = "London"
        hotel.rating = 4.5
        hotel.amenities = "WiFi, Pool"

        with patch("backend.tools.search_tools.get_hotels_by_location", return_value=[hotel]), \
             patch("backend.tools.search_tools.logger"):
            from backend.tools.search_tools import search_hotels
            result = search_hotels.invoke({"location": "London"})

        assert "Grand Hotel" in result
        assert "London" in result
        assert "1" in result

    def test_no_hotels_found(self):
        with patch("backend.tools.search_tools.get_hotels_by_location", return_value=[]), \
             patch("backend.tools.search_tools.logger"):
            from backend.tools.search_tools import search_hotels
            result = search_hotels.invoke({"location": "Nowhere"})

        assert "No hotels found" in result

    def test_service_exception_handled(self):
        with patch("backend.tools.search_tools.get_hotels_by_location", side_effect=Exception("DB down")), \
             patch("backend.tools.search_tools.logger"):
            from backend.tools.search_tools import search_hotels
            result = search_hotels.invoke({"location": "London"})

        assert "Error" in result
        assert "DB down" in result


# ---------------------------------------------------------------------------
# check_hotel_availability
# ---------------------------------------------------------------------------

class TestCheckHotelAvailabilityTool:

    _DEFAULT_ROOMS = [
        {"room_type": "Standard", "capacity": 2, "price_per_night": 120.0, "available_rooms": 3}
    ]

    def _mock_availability_result(self, success=True, rooms=_DEFAULT_ROOMS):
        return {
            "success": success,
            "message": "ok" if success else "Hotel not found",
            "hotel_name": "Grand Hotel",
            "location": "London",
            "rating": 4.5,
            "check_in": "2026-05-01",
            "check_out": "2026-05-05",
            "guests": 2,
            "available_room_types": rooms,
        }

    def test_available_rooms_returned(self):
        with patch("backend.tools.availability_tools.check_hotel_availability_service",
                   return_value=self._mock_availability_result()), \
             patch("backend.tools.availability_tools.logger"):
            from backend.tools.availability_tools import check_hotel_availability
            result = check_hotel_availability.invoke({
                "hotel_id": 1, "check_in": "2026-05-01",
                "check_out": "2026-05-05", "guests": 2
            })

        assert "Standard" in result
        assert "120" in result

    def test_no_rooms_available(self):
        with patch("backend.tools.availability_tools.check_hotel_availability_service",
                   return_value=self._mock_availability_result(rooms=[])), \
             patch("backend.tools.availability_tools.logger"):
            from backend.tools.availability_tools import check_hotel_availability
            result = check_hotel_availability.invoke({
                "hotel_id": 1, "check_in": "2026-05-01",
                "check_out": "2026-05-05", "guests": 2
            })

        assert "No rooms available" in result

    def test_service_failure(self):
        with patch("backend.tools.availability_tools.check_hotel_availability_service",
                   return_value={"success": False, "message": "Hotel not found"}), \
             patch("backend.tools.availability_tools.logger"):
            from backend.tools.availability_tools import check_hotel_availability
            result = check_hotel_availability.invoke({
                "hotel_id": 99, "check_in": "2026-05-01",
                "check_out": "2026-05-05", "guests": 2
            })

        assert "Hotel not found" in result

    def test_invalid_date_format_handled(self):
        with patch("backend.tools.availability_tools.logger"):
            from backend.tools.availability_tools import check_hotel_availability
            result = check_hotel_availability.invoke({
                "hotel_id": 1, "check_in": "not-a-date",
                "check_out": "2026-05-05", "guests": 2
            })

        assert "Error" in result


# ---------------------------------------------------------------------------
# calculate_price
# ---------------------------------------------------------------------------

class TestCalculatePriceTool:

    def test_price_breakdown_returned(self):
        mock_result = {
            "success": True,
            "hotel_name": "Grand Hotel",
            "room_type": "Standard",
            "price_per_night": 120.0,
            "nights": 4,
            "check_in": "2026-05-01",
            "check_out": "2026-05-05",
            "guests": 2,
            "total_price": 480.0,
            "currency": "GBP",
        }
        with patch("backend.tools.price_tools.calculate_price_service", return_value=mock_result):
            from backend.tools.price_tools import calculate_price
            result = calculate_price.invoke({
                "hotel_id": 1, "room_type": "Standard",
                "check_in": "2026-05-01", "check_out": "2026-05-05", "guests": 2
            })

        assert "480" in result
        assert "120" in result
        assert "4" in result

    def test_failure_message_returned(self):
        with patch("backend.tools.price_tools.calculate_price_service",
                   return_value={"success": False, "message": "Room not found"}):
            from backend.tools.price_tools import calculate_price
            result = calculate_price.invoke({
                "hotel_id": 1, "room_type": "Suite",
                "check_in": "2026-05-01", "check_out": "2026-05-05", "guests": 2
            })

        assert "failed" in result.lower()
        assert "Room not found" in result


# ---------------------------------------------------------------------------
# process_payment
# ---------------------------------------------------------------------------

class TestProcessPaymentTool:

    def test_successful_payment(self):
        mock_result = {
            "success": True,
            "transaction_id": "TXN-ABCDEF012345",
            "amount": 480.0,
            "currency": "GBP",
            "card_last4": "1111",
            "cardholder_name": "Alice",
        }
        with patch("backend.tools.payment_tools.process_payment_service", return_value=mock_result), \
             patch("backend.tools.payment_tools.langfuse_context"):
            from backend.tools.payment_tools import process_payment
            result = process_payment.invoke({
                "amount": 480.0, "currency": "GBP",
                "card_number": "4111111111111111", "cardholder_name": "Alice"
            })

        assert "TXN-ABCDEF012345" in result
        assert "approved" in result.lower()
        assert "1111" in result

    def test_failed_payment(self):
        with patch("backend.tools.payment_tools.process_payment_service",
                   return_value={"success": False, "message": "Insufficient funds"}), \
             patch("backend.tools.payment_tools.langfuse_context"):
            from backend.tools.payment_tools import process_payment
            result = process_payment.invoke({
                "amount": 480.0, "currency": "GBP",
                "card_number": "4111111111111111", "cardholder_name": "Alice"
            })

        assert "failed" in result.lower()
        assert "Insufficient funds" in result


# ---------------------------------------------------------------------------
# create_booking
# ---------------------------------------------------------------------------

class TestCreateBookingTool:

    def test_successful_booking(self):
        mock_result = {
            "success": True,
            "booking_reference": "BK-001",
            "hotel_name": "Grand Hotel",
            "room_type": "Standard",
            "check_in": "2026-05-01",
            "check_out": "2026-05-05",
            "guests": 2,
            "booked_price_per_night": 120.0,
            "total_price": 480.0,
            "currency": "GBP",
            "status": "confirmed",
            "payment_transaction_id": "TXN-ABCDEF012345",
        }
        with patch("backend.tools.booking_tools.create_booking_service", return_value=mock_result):
            from backend.tools.booking_tools import create_booking
            result = create_booking.invoke({
                "hotel_id": 1,
                "check_in": "2026-05-01",
                "check_out": "2026-05-05",
                "guests": 2,
                "user_name": "Alice",
                "user_email": "alice@example.com",
                "room_type": "Standard",
                "payment_transaction_id": "TXN-ABCDEF012345",
            })

        assert "BK-001" in result
        assert "Grand Hotel" in result
        assert "confirmed" in result

    def test_booking_failure(self):
        with patch("backend.tools.booking_tools.create_booking_service",
                   return_value={"success": False, "message": "No rooms left"}):
            from backend.tools.booking_tools import create_booking
            result = create_booking.invoke({
                "hotel_id": 1,
                "check_in": "2026-05-01",
                "check_out": "2026-05-05",
                "guests": 2,
                "user_name": "Alice",
                "user_email": "alice@example.com",
            })

        assert "failed" in result.lower()
        assert "No rooms left" in result


# ---------------------------------------------------------------------------
# check_payment_status
# ---------------------------------------------------------------------------

import sys as _sys

def _db_ctx(record):
    """
    Context manager: temporarily sets SessionLocal on the conftest db stub
    so the tool function (which captured it at import time via
    'from backend.db.database import SessionLocal') uses our mock.
    """
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = record
        sl = MagicMock(return_value=mock_db)
        # Patch on the module-level name in both the stub and the tool module
        with patch("backend.tools.check_payment_status.SessionLocal", sl), \
             patch("backend.tools.lookup_company_contact.SessionLocal", sl):
            yield mock_db

    return _ctx()


class TestCheckPaymentStatusTool:

    def test_record_found(self):
        record = MagicMock()
        record.invoice_number = "INV-001"
        record.vendor_name = "Acme Corp"
        record.payment_status = "paid"
        record.amount_due = 1000.0
        record.amount_paid = 1000.0
        record.due_date = "2026-04-01"
        record.payment_date = "2026-03-20"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = record
        sl = MagicMock(return_value=mock_db)

        from backend.tools.check_payment_status import check_payment_status
        with patch.object(
            _sys.modules["backend.tools.check_payment_status"], "SessionLocal", sl
        ):
            result_str = check_payment_status.invoke({"invoice_number": "INV-001"})

        result = json.loads(result_str)
        assert result["found"] is True
        assert result["payment_status"] == "paid"
        assert result["invoice_number"] == "INV-001"

    def test_record_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        sl = MagicMock(return_value=mock_db)

        from backend.tools.check_payment_status import check_payment_status
        with patch.object(
            _sys.modules["backend.tools.check_payment_status"], "SessionLocal", sl
        ):
            result_str = check_payment_status.invoke({"invoice_number": "INV-999"})

        result = json.loads(result_str)
        assert result["found"] is False
        assert "INV-999" in result["invoice_number"]

    def test_db_exception_handled(self):
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB timeout")
        sl = MagicMock(return_value=mock_db)

        from backend.tools.check_payment_status import check_payment_status
        with patch.object(
            _sys.modules["backend.tools.check_payment_status"], "SessionLocal", sl
        ):
            result_str = check_payment_status.invoke({"invoice_number": "INV-001"})

        result = json.loads(result_str)
        assert "error" in result


# ---------------------------------------------------------------------------
# lookup_company_contact
# ---------------------------------------------------------------------------

class TestLookupCompanyContactTool:

    def _make_record(self):
        r = MagicMock()
        r.company_name = "Acme Corp"
        r.phone_number = "+44 20 1234 5678"
        r.email = "contact@acme.com"
        r.website = "https://acme.com"
        r.contact_person = "Bob"
        r.address = "123 High Street, London"
        return r

    def test_found_by_company_name(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = self._make_record()
        sl = MagicMock(return_value=mock_db)

        from backend.tools.lookup_company_contact import lookup_company_contact
        with patch.object(
            _sys.modules["backend.tools.lookup_company_contact"], "SessionLocal", sl
        ):
            result_str = lookup_company_contact.invoke({"company_name": "Acme"})

        result = json.loads(result_str)
        assert result["found"] is True
        assert result["company_name"] == "Acme Corp"
        assert "acme.com" in result["email"]

    def test_not_found_returns_found_false(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        sl = MagicMock(return_value=mock_db)

        from backend.tools.lookup_company_contact import lookup_company_contact
        with patch.object(
            _sys.modules["backend.tools.lookup_company_contact"], "SessionLocal", sl
        ):
            result_str = lookup_company_contact.invoke({"company_name": "Unknown Corp"})

        result = json.loads(result_str)
        assert result["found"] is False

    def test_db_exception_handled(self):
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Connection error")
        sl = MagicMock(return_value=mock_db)

        from backend.tools.lookup_company_contact import lookup_company_contact
        with patch.object(
            _sys.modules["backend.tools.lookup_company_contact"], "SessionLocal", sl
        ):
            result_str = lookup_company_contact.invoke({"company_name": "Acme"})

        result = json.loads(result_str)
        assert "error" in result


# ---------------------------------------------------------------------------
# extract_invoice_data
# ---------------------------------------------------------------------------

class TestExtractInvoiceDataTool:

    def test_file_not_found_returns_error(self):
        with patch("backend.tools.extract_invoice_data.Path") as mock_path_cls, \
             patch("backend.tools.extract_invoice_data._get_client"):
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path.suffix = ".pdf"
            mock_path_cls.return_value = mock_path

            from backend.tools.extract_invoice_data import extract_invoice_data
            result_str = extract_invoice_data.invoke({"file_path": "/nonexistent/invoice.pdf"})

        result = json.loads(result_str)
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_pdf_extraction_returns_json(self):
        mock_json = '{"invoice_number": "INV-001", "vendor_name": "Acme", "total_amount": 500.0}'
        mock_response = MagicMock()
        mock_response.choices[0].message.content = mock_json

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        # Build a real-ish Path stub: exists()=True, suffix=".pdf"
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.suffix = ".pdf"

        # pdfplumber context manager stub
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Invoice text"
        mock_pdf_ctx = MagicMock()
        mock_pdf_ctx.__enter__ = MagicMock(return_value=mock_pdf_ctx)
        mock_pdf_ctx.__exit__ = MagicMock(return_value=False)
        mock_pdf_ctx.pages = [mock_page]

        with patch("backend.tools.extract_invoice_data.Path", return_value=mock_path), \
             patch("backend.tools.extract_invoice_data._get_client", return_value=mock_client), \
             patch("backend.tools.extract_invoice_data.pdfplumber") as mock_plumber, \
             patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4"}):

            mock_plumber.open.return_value = mock_pdf_ctx

            from backend.tools.extract_invoice_data import extract_invoice_data
            result_str = extract_invoice_data.invoke({"file_path": "/app/uploads/invoice.pdf"})

        result = json.loads(result_str)
        assert result["invoice_number"] == "INV-001"
        assert result["vendor_name"] == "Acme"
