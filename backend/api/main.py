import time
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from backend.utils.langfuse_compat import observe, langfuse_context, propagate_attributes

from backend.graph.graph import hotel_agent
from backend.utils.logger import logger
from backend.guardrails.input_guardrail import validate_input
from backend.guardrails.output_guardrail import sanitize_output, sanitize_error_message
from backend.config import settings
from backend.evaluation.evaluator import evaluate_response
from backend.observability.tracing import trace_all

app = FastAPI()


# ── S3 helper (lazy import so boto3 is optional in dev) ───────────────────────

def _upload_to_s3(file_bytes: bytes, key: str) -> str:
    """Upload bytes to S3 and return the S3 URI (s3://bucket/key)."""
    import boto3
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=file_bytes,
    )
    return f"s3://{settings.S3_BUCKET}/{key}"

# ── Langfuse startup diagnostics ──────────────────────────────────────────────
try:
    import langfuse as _lf
    logger.info(f"📦 langfuse version: {_lf.__version__}")
except Exception:
    logger.warning("⚠️ Could not read langfuse version")

from backend.utils.langfuse_compat import LANGFUSE_DECORATORS
if LANGFUSE_DECORATORS:
    logger.info("✅ langfuse.decorators loaded — @observe tracing active")
else:
    logger.warning("⚠️ langfuse.decorators NOT available — @observe is a no-op")

try:
    from langfuse import Langfuse
    _test = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
    )
    logger.info(f"✅ Langfuse client connected to {settings.LANGFUSE_BASE_URL}")
    _methods = [m for m in dir(_test) if not m.startswith("_")]
    logger.info(f"📋 Langfuse client methods: {_methods}")
except Exception as e:
    logger.warning(f"⚠️ Langfuse client failed to initialise: {e}")

# In-memory session store for development
SESSION_STORE = {}

UPLOAD_DIR = Path("/app/uploads")


# ── Invoice upload endpoint ────────────────────────────────────────────────────
@app.post("/upload-invoice")
async def upload_invoice(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        return {"error": "Only PDF, PNG, and JPG files are supported."}

    file_id = str(uuid.uuid4())
    file_bytes = await file.read()

    if settings.S3_BUCKET:
        # ── Production: store in S3 ───────────────────────────────────────────
        key = f"{settings.S3_PREFIX}/{file_id}{suffix}"
        try:
            s3_uri = _upload_to_s3(file_bytes, key)
            logger.info(f"📄 Invoice uploaded to S3: {s3_uri}")
            return {"file_path": s3_uri}
        except Exception as e:
            logger.exception("❌ S3 upload failed")
            return {"error": f"Upload failed: {e}"}
    else:
        # ── Development: store locally ────────────────────────────────────────
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPLOAD_DIR / f"{file_id}{suffix}"
        dest.write_bytes(file_bytes)
        logger.info(f"📄 Invoice uploaded locally: {dest}")
        return {"file_path": str(dest)}


# ── Request schema ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    user_name: str = ""
    user_email: str = ""
    session_id: str = ""
    invoice_file_path: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────
def build_followup_question(missing_fields: list[str]) -> str:
    field_labels = {
        "location": "location",
        "hotel_id": "hotel ID",
        "check_in": "check-in date",
        "check_out": "check-out date",
        "guests": "number of guests",
        "room_type": "room type",
        "user_name": "your name",
        "user_email": "your email",
        "invoice_file_path": "an invoice file (please upload one using the sidebar)",
    }

    readable = [field_labels.get(f, f) for f in missing_fields]

    if not readable:
        return "Could you provide the missing booking details?"

    if len(readable) == 1:
        return f"Please provide the {readable[0]}."

    if len(readable) == 2:
        return f"Please provide the {readable[0]} and {readable[1]}."

    return (
        "Please provide the following missing details: "
        + ", ".join(readable[:-1])
        + f", and {readable[-1]}."
    )


def get_or_create_session(session_id: str, user_name: str, user_email: str) -> dict:
    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = {
            "messages": [],
            "user_name": user_name or "",
            "user_email": user_email or "",
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
    return SESSION_STORE[session_id]


# ── Langfuse @observe — wraps the agent invocation ────────────────────────────
@observe(name="hotel_chat")
def _run_hotel_agent(state: dict, session_id: str) -> tuple[dict, str]:
    """
    Runs the LangGraph hotel agent.
    Decorated with @observe so every call creates a Langfuse trace.
    Nested @observe spans (orchestrator, booking, search) appear as children.
    Returns (result dict, langfuse_trace_id).
    """
    user_message = next(
        (msg.content for msg in reversed(state.get("messages", [])) if isinstance(msg, HumanMessage)),
        "",
    )

    langfuse_context.update_current_observation(input=user_message)

    # propagate_attributes sets session_id and user_id on all child spans (required for Sessions in Langfuse 4.x)
    with propagate_attributes(
        session_id=session_id,
        user_id=state.get("user_name") or "anonymous",
    ):
        result = hotel_agent.invoke(state)

    agent_output = ""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, (ToolMessage, AIMessage)):
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                agent_output = content
                break
    langfuse_context.update_current_trace(output=agent_output)

    trace_id = langfuse_context.get_current_trace_id()
    return result, trace_id


# ── Chat endpoint ─────────────────────────────────────────────────────────────
@app.post("/chat")
def chat(request: ChatRequest):
    logger.info("📩 /chat request received")

    session_id = request.session_id or request.user_email or str(uuid.uuid4())
    state = get_or_create_session(session_id, request.user_name, request.user_email)

    # Keep latest profile details
    if request.user_name:
        state["user_name"] = request.user_name
    if request.user_email:
        state["user_email"] = request.user_email
    if request.invoice_file_path:
        state["invoice_file_path"] = request.invoice_file_path

    # Input guardrail
    guardrail_result = validate_input(request.message)
    if not guardrail_result["allowed"]:
        return {
            "response": guardrail_result["message"],
            "session_id": session_id,
        }

    normalized_message = guardrail_result["normalized_message"]
    state["messages"].append(HumanMessage(content=normalized_message))

    logger.info(
        f"🧠 Session before invoke | "
        f"location={state.get('location')}, hotel_id={state.get('hotel_id')}, "
        f"check_in={state.get('check_in')}, check_out={state.get('check_out')}, "
        f"guests={state.get('guests')}, room_type={state.get('room_type')}"
    )

    # Track whether booking agent was actively handling a step before this call.
    # If so, we must use the agent's output message — not the orchestrator's intent.
    booking_was_active = state.get("booking_step") in (
        "price_shown", "awaiting_payment", "payment_done", "done"
    )

    # Run graph (traced by Langfuse via @observe)
    try:
        start = time.time()
        result, lf_trace_id = _run_hotel_agent(state, session_id)
        duration = time.time() - start
    except Exception as e:
        logger.exception("❌ Unhandled backend error during hotel_agent.invoke")
        return {
            "response": sanitize_error_message(e),
            "session_id": session_id,
        }

    # Persist extracted scalar state
    for key in [
        "location",
        "hotel_id",
        "check_in",
        "check_out",
        "guests",
        "room_type",
        "room_type_id",
        "intent",
        "selected_agent",
        "missing_fields",
        "user_name",
        "user_email",
        "invoice_file_path",
    ]:
        if key in result and result[key] is not None:
            state[key] = result[key]

    # booking_step must persist even when empty string (allows reset after booking)
    if "booking_step" in result:
        state["booking_step"] = result["booking_step"]
    if "payment_transaction_id" in result and result["payment_transaction_id"] is not None:
        state["payment_transaction_id"] = result["payment_transaction_id"]

    logger.info(
        f"🧠 Saved session state: "
        f"location={state.get('location')}, hotel_id={state.get('hotel_id')}, "
        f"check_in={state.get('check_in')}, check_out={state.get('check_out')}, "
        f"guests={state.get('guests')}, room_type={state.get('room_type')}, "
        f"intent={state.get('intent')}, missing_fields={state.get('missing_fields')}"
    )

    # Build reply
    # When the booking agent was actively running (bypassing the orchestrator),
    # always use the agent's output message — never the orchestrator's intent-based reply.
    if booking_was_active:
        reply = None
        result_messages = result.get("messages", [])
        if result_messages and isinstance(result_messages[-1], AIMessage):
            content = getattr(result_messages[-1], "content", None)
            if isinstance(content, str) and content.strip():
                reply = content
        if not reply:
            for msg in reversed(result_messages):
                if isinstance(msg, AIMessage):
                    content = getattr(msg, "content", None)
                    if isinstance(content, str) and content.strip():
                        reply = content
                        break
        if not reply:
            reply = "Sorry, I couldn't get a response from the booking agent."

    elif state.get("intent") == "ask_followup":
        reply = build_followup_question(state.get("missing_fields", []))

    elif state.get("intent") == "confirm_booking":
        reply = (
            f"Please confirm your booking details:\n\n"
            f"🏨 Hotel ID : {state.get('hotel_id')}\n"
            f"📅 Check-in : {state.get('check_in')}\n"
            f"📅 Check-out: {state.get('check_out')}\n"
            f"👥 Guests  : {state.get('guests')}\n"
            f"🛏️ Room type: {state.get('room_type') or 'Standard'}\n\n"
            f"Type **yes** or **confirm** to complete the booking, or **no** to cancel."
        )

    elif state.get("intent") == "reject_request":
        reply = "I can help with hotel search, availability checks, bookings, and invoices."

    else:
        reply = None
        result_messages = result.get("messages", [])

        # If the final message is an AIMessage, prefer it — the agent has
        # synthesised all tool results into a user-facing response (e.g. asking
        # for card details, or producing the final booking confirmation).
        if result_messages and isinstance(result_messages[-1], AIMessage):
            content = getattr(result_messages[-1], "content", None)
            if isinstance(content, str) and content.strip():
                reply = content

        # Otherwise fall back to the last ToolMessage (search/availability flows
        # end with a ToolMessage and no follow-up AIMessage).
        if not reply:
            for msg in reversed(result_messages):
                if isinstance(msg, ToolMessage):
                    content = getattr(msg, "content", None)
                    if isinstance(content, str) and content.strip():
                        reply = content
                        break

        # Final fallback: any AIMessage
        if not reply:
            for msg in reversed(result_messages):
                if isinstance(msg, AIMessage):
                    content = getattr(msg, "content", None)
                    if isinstance(content, str) and content.strip():
                        reply = content
                        break

        if not reply:
            reply = "Sorry, I couldn't find a valid response."

    # Output guardrail
    reply = sanitize_output(reply)

    # Persist only conversational messages across turns
    state["messages"].append(AIMessage(content=reply))

    # ── Evaluation + Observability ────────────────────────────────────────────
    evaluate_response(request.message, reply, trace_id=lf_trace_id)
    trace_all(request.message, reply, user_name=state.get("user_name", ""), duration=duration)

    return {
        "response": reply,
        "session_id": session_id,
    }
