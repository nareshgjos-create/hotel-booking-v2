from pydantic import BaseModel, Field
from typing import Literal, Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from backend.utils.langfuse_compat import observe, langfuse_context
from backend.config import settings
from backend.utils.logger import logger


class RoutingDecision(BaseModel):
    intent: Literal[
        "search_hotels",
        "check_availability",
        "create_booking",
        "confirm_booking",
        "ask_followup",
        "process_invoice",
        "reject_request"
    ] = Field(...)

    location: Optional[str] = None
    hotel_id: Optional[int] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    guests: Optional[int] = None
    room_type: Optional[str] = None
    invoice_file_path: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)


orchestrator_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0
).with_structured_output(RoutingDecision)


ORCHESTRATOR_PROMPT = """
You are the Orchestrator Agent for a hotel booking system.

Your responsibilities:
1. Understand the user's latest request
2. Extract any hotel-related fields if clearly present
3. Decide the safest next action
4. Never invent missing information

Allowed intents:
- search_hotels
- check_availability
- confirm_booking   ← user said "book" but hasn't explicitly confirmed yet
- create_booking    ← user has confirmed they want to proceed
- ask_followup
- reject_request

Field extraction rules:
- location: city or destination name
- hotel_id: integer only if explicitly provided
- check_in/check_out: only if clearly given
- guests: integer only if clearly given
- room_type: only if explicitly stated
- missing_fields: list only the fields required for the chosen action

Routing rules:
- Use search_hotels when the user wants to find hotels in a place
- Use check_availability when the user asks whether a specific hotel is available
- Use confirm_booking when the user mentions booking/reserving but has NOT yet explicitly confirmed (e.g. "book hotel 1", "I want to book")
- Use create_booking ONLY when the user explicitly confirms after being shown a summary (e.g. "yes", "confirm", "go ahead", "proceed")
- Use process_invoice when the user wants to process, extract, or check an invoice file (e.g. "process invoice", "extract invoice data", "check payment status for invoice")
- Use ask_followup if required information is missing
- Use reject_request for unrelated or unsupported requests

Important safety rules:
- Never invent dates, hotel IDs, guest counts, names, or emails
- If the user asks to book but required details are missing, return ask_followup
- If the request is unrelated to hotel search, availability, or booking, return reject_request
- If the user refers to "this hotel" or "that hotel" but no hotel_id is available, return ask_followup
- NEVER use create_booking on the first booking request — always confirm_booking first
- If the user is providing follow-up details (such as name, email, dates, guests, room type, card number, cardholder name, payment details) in response to a previous question in the conversation, treat it as a continuation of the most recent booking intent — use confirm_booking or ask_followup, never reject_request
"""


def _post_validate_decision(state: dict, decision: RoutingDecision) -> dict:
    """
    Deterministic guardrails after LLM routing.
    This keeps orchestration reliable even if the model is imperfect.
    """
    intent = decision.intent
    missing_fields = list(decision.missing_fields)

    user_name = state.get("user_name")
    user_email = state.get("user_email")

    def add_missing(field_name: str):
        if field_name not in missing_fields:
            missing_fields.append(field_name)

    if intent == "search_hotels":
        location = decision.location or state.get("location")
        if not location:
            intent = "ask_followup"
            add_missing("location")

    elif intent == "check_availability":
        hotel_id = decision.hotel_id or state.get("hotel_id")
        check_in = decision.check_in or state.get("check_in")
        check_out = decision.check_out or state.get("check_out")
        guests = decision.guests or state.get("guests")

        if not hotel_id:
            add_missing("hotel_id")
        if not check_in:
            add_missing("check_in")
        if not check_out:
            add_missing("check_out")
        if not guests:
            add_missing("guests")

        if missing_fields:
            intent = "ask_followup"

    elif intent == "create_booking":
        hotel_id = decision.hotel_id or state.get("hotel_id")
        check_in = decision.check_in or state.get("check_in")
        check_out = decision.check_out or state.get("check_out")
        guests = decision.guests or state.get("guests")
        room_type = decision.room_type or state.get("room_type")

        if not hotel_id:
            add_missing("hotel_id")
        if not check_in:
            add_missing("check_in")
        if not check_out:
            add_missing("check_out")
        if not guests:
            add_missing("guests")
        if not room_type and not state.get("room_type_id"):
            add_missing("room_type")
        if not user_name:
            add_missing("user_name")
        if not user_email:
            add_missing("user_email")

        if missing_fields:
            intent = "ask_followup"

    elif intent == "process_invoice":
        # Only trust the server-side path set by the upload endpoint.
        # Never use decision.invoice_file_path — the LLM may extract a bare
        # filename like "invoice.pdf" from the message text, which will not
        # resolve to a real file.
        if not state.get("invoice_file_path"):
            intent = "ask_followup"
            add_missing("invoice_file_path")

    # Routing after merge:
    if intent in ["search_hotels", "check_availability"]:
        selected_agent = "search_availability_agent"
    elif intent == "confirm_booking":
        selected_agent = "booking_agent"
    elif intent == "create_booking":
        selected_agent = "booking_agent"
    elif intent == "process_invoice":
        selected_agent = "invoice_agent"
    else:
        selected_agent = None

    return {
        "intent": intent,
        "location": decision.location or state.get("location"),
        "hotel_id": decision.hotel_id or state.get("hotel_id"),
        "check_in": decision.check_in or state.get("check_in"),
        "check_out": decision.check_out or state.get("check_out"),
        "guests": decision.guests or state.get("guests"),
        "room_type": decision.room_type or state.get("room_type"),
        "invoice_file_path": state.get("invoice_file_path"),
        "missing_fields": missing_fields,
        "selected_agent": selected_agent,
    }


@observe(name="orchestrator_agent")
def run_orchestrator_agent(state: dict) -> dict:
    langfuse_context.update_current_observation(
        input={"last_message": state["messages"][-1].content if state["messages"] else ""},
    )
    logger.info("🧭 Orchestrator Agent running...")

    messages = [SystemMessage(content=ORCHESTRATOR_PROMPT)] + state["messages"][-8:]
    decision = orchestrator_llm.invoke(messages)

    logger.info(f"✅ Orchestrator decided intent: {decision.intent}")

    routed_state = _post_validate_decision(state, decision)

    langfuse_context.update_current_observation(
        output={"intent": routed_state["intent"], "selected_agent": routed_state["selected_agent"]},
    )

    logger.info(
        f"🧭 Final routing → intent={routed_state['intent']} | "
        f"selected_agent={routed_state['selected_agent']} | "
        f"missing_fields={routed_state['missing_fields']}"
    )

    return routed_state