"""Tests for backend/api/main.py — build_followup_question, get_or_create_session, /chat and /upload-invoice endpoints."""
import io
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


# ---------------------------------------------------------------------------
# Patch all heavy dependencies before importing the app
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def patch_app_deps():
    with patch("backend.api.main.hotel_agent"), \
         patch("backend.api.main.validate_input", return_value={"allowed": True, "message": "ok", "normalized_message": "test"}), \
         patch("backend.api.main.sanitize_output", side_effect=lambda x: x), \
         patch("backend.api.main.sanitize_error_message", return_value="error"), \
         patch("backend.api.main.evaluate_response"), \
         patch("backend.api.main.trace_all"), \
         patch("backend.api.main.langfuse_context"), \
         patch("backend.api.main.logger"), \
         patch("backend.api.main.UPLOAD_DIR"):
        yield


from backend.api.main import app, build_followup_question, get_or_create_session, SESSION_STORE  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# build_followup_question
# ---------------------------------------------------------------------------

class TestBuildFollowupQuestion:

    def test_empty_fields_returns_generic(self):
        result = build_followup_question([])
        assert result  # non-empty

    def test_single_known_field(self):
        result = build_followup_question(["location"])
        assert "location" in result

    def test_two_fields(self):
        result = build_followup_question(["check_in", "check_out"])
        assert "check-in" in result
        assert "check-out" in result

    def test_three_fields(self):
        result = build_followup_question(["hotel_id", "check_in", "guests"])
        assert "hotel ID" in result
        assert "check-in date" in result
        assert "number of guests" in result

    def test_invoice_field_mentions_upload(self):
        result = build_followup_question(["invoice_file_path"])
        assert "upload" in result.lower() or "sidebar" in result.lower()

    def test_unknown_field_echoed(self):
        result = build_followup_question(["mystery_field"])
        assert "mystery_field" in result


# ---------------------------------------------------------------------------
# get_or_create_session
# ---------------------------------------------------------------------------

class TestGetOrCreateSession:

    def setup_method(self):
        SESSION_STORE.clear()

    def test_creates_new_session(self):
        session = get_or_create_session("sess-new", "Alice", "alice@example.com")
        assert session["user_name"] == "Alice"
        assert session["messages"] == []

    def test_returns_existing_session(self):
        get_or_create_session("sess-exist", "Alice", "alice@example.com")
        session = get_or_create_session("sess-exist", "Bob", "bob@example.com")
        # Should not overwrite existing session
        assert session["user_name"] == "Alice"

    def test_all_required_keys_present(self):
        session = get_or_create_session("sess-keys", "", "")
        required = [
            "messages", "user_name", "user_email", "location", "hotel_id",
            "check_in", "check_out", "guests", "room_type", "room_type_id",
            "intent", "selected_agent", "missing_fields", "booking_step",
            "payment_transaction_id", "invoice_file_path",
        ]
        for key in required:
            assert key in session, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# /upload-invoice endpoint
# ---------------------------------------------------------------------------

class TestUploadInvoiceEndpoint:

    def test_rejects_unsupported_format(self):
        resp = client.post(
            "/upload-invoice",
            files={"file": ("malware.exe", b"data", "application/octet-stream")},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_accepts_pdf(self, tmp_path):
        pdf_bytes = b"%PDF-1.4 fake content"
        with patch("backend.api.main.UPLOAD_DIR", tmp_path), \
             patch("shutil.copyfileobj"):
            resp = client.post(
                "/upload-invoice",
                files={"file": ("invoice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
        # Either success with file_path or error — just must not 500
        assert resp.status_code == 200

    def test_accepts_png(self, tmp_path):
        with patch("backend.api.main.UPLOAD_DIR", tmp_path), \
             patch("shutil.copyfileobj"):
            resp = client.post(
                "/upload-invoice",
                files={"file": ("invoice.png", io.BytesIO(b"PNG data"), "image/png")},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /chat endpoint — intent-based reply routing
# ---------------------------------------------------------------------------

class TestChatEndpoint:

    def setup_method(self):
        SESSION_STORE.clear()

    def _mock_agent_result(self, intent, ai_content="response", booking_step=""):
        result = {
            "messages": [AIMessage(content=ai_content)],
            "intent": intent,
            "selected_agent": None,
            "missing_fields": [],
            "location": None,
            "hotel_id": None,
            "check_in": None,
            "check_out": None,
            "guests": None,
            "room_type": None,
            "room_type_id": None,
            "user_name": "",
            "user_email": "",
            "invoice_file_path": None,
            "booking_step": booking_step,
            "payment_transaction_id": None,
        }
        return result

    def test_guardrail_blocks_input(self):
        with patch("backend.api.main.validate_input",
                   return_value={"allowed": False, "message": "Not allowed", "normalized_message": ""}):
            resp = client.post("/chat", json={"message": "hack the system"})
        assert resp.status_code == 200
        assert resp.json()["response"] == "Not allowed"

    def test_ask_followup_returns_missing_field_message(self):
        result = self._mock_agent_result("ask_followup")
        result["missing_fields"] = ["location"]

        with patch("backend.api.main._run_hotel_agent", return_value=(result, "trace-1")), \
             patch("backend.api.main.validate_input",
                   return_value={"allowed": True, "message": "ok", "normalized_message": "find hotels"}):
            resp = client.post("/chat", json={"message": "find hotels", "session_id": "s1"})

        assert resp.status_code == 200
        assert "location" in resp.json()["response"].lower()

    def test_confirm_booking_returns_summary(self):
        result = self._mock_agent_result("confirm_booking")
        result.update({"hotel_id": 1, "check_in": "2026-05-01", "check_out": "2026-05-05", "guests": 2})

        with patch("backend.api.main._run_hotel_agent", return_value=(result, "trace-2")), \
             patch("backend.api.main.validate_input",
                   return_value={"allowed": True, "message": "ok", "normalized_message": "book hotel"}):
            resp = client.post("/chat", json={
                "message": "book hotel", "session_id": "s2",
                "user_name": "Alice", "user_email": "alice@example.com"
            })

        body = resp.json()["response"]
        assert "confirm" in body.lower() or "hotel" in body.lower()

    def test_reject_request_returns_help_message(self):
        result = self._mock_agent_result("reject_request")

        with patch("backend.api.main._run_hotel_agent", return_value=(result, "trace-3")), \
             patch("backend.api.main.validate_input",
                   return_value={"allowed": True, "message": "ok", "normalized_message": "what is AI?"}):
            resp = client.post("/chat", json={"message": "what is AI?", "session_id": "s3"})

        assert "hotel" in resp.json()["response"].lower() or "invoice" in resp.json()["response"].lower()

    def test_invoice_path_passed_to_state(self):
        result = self._mock_agent_result("process_invoice", ai_content="Invoice processed.")

        with patch("backend.api.main._run_hotel_agent", return_value=(result, "trace-4")) as mock_agent, \
             patch("backend.api.main.validate_input",
                   return_value={"allowed": True, "message": "ok", "normalized_message": "process invoice"}):
            resp = client.post("/chat", json={
                "message": "process invoice",
                "session_id": "s4",
                "invoice_file_path": "/app/uploads/real.pdf"
            })

        assert resp.status_code == 200
        # Verify the state passed to the agent had the correct file path
        called_state = mock_agent.call_args[0][0]
        assert called_state["invoice_file_path"] == "/app/uploads/real.pdf"

    def test_backend_exception_returns_sanitized_error(self):
        with patch("backend.api.main._run_hotel_agent", side_effect=Exception("crash")), \
             patch("backend.api.main.validate_input",
                   return_value={"allowed": True, "message": "ok", "normalized_message": "book hotel"}), \
             patch("backend.api.main.sanitize_error_message", return_value="Something went wrong."):
            resp = client.post("/chat", json={"message": "book hotel", "session_id": "s5"})

        assert resp.status_code == 200
        assert "Something went wrong" in resp.json()["response"]

    def test_session_id_returned(self):
        result = self._mock_agent_result("reject_request")

        with patch("backend.api.main._run_hotel_agent", return_value=(result, "trace-5")), \
             patch("backend.api.main.validate_input",
                   return_value={"allowed": True, "message": "ok", "normalized_message": "hi"}):
            resp = client.post("/chat", json={"message": "hi", "session_id": "my-session"})

        assert resp.json()["session_id"] == "my-session"
