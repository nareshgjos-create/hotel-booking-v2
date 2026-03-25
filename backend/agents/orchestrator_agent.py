from pydantic import BaseModel, Field
from typing import Literal, Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from backend.config import settings
from backend.utils.logger import logger


class RoutingDecision(BaseModel):
    intent: Literal[
        "search_hotels",
        "check_availability",
        "create_booking",
        "ask_followup",
        "reject_request"
    ] = Field(...)

    location: Optional[str] = None
    hotel_id: Optional[int] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    guests: Optional[int] = None
    room_type: Optional[str] = None
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
2. Extract any booking-related fields if clearly present
3. Decide the safest next action
4. Never invent missing information

Allowed intents:
- search_hotels
- check_availability
- create_booking
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
- Use create_booking only when the user clearly wants to reserve/book
- Use ask_followup if required information is missing
- Use reject_request for unrelated or unsupported requests

Important safety rules:
- Never invent dates, hotel IDs, guest counts, names, or emails
- If the user asks to book but required details are missing, return ask_followup
- If the request is unrelated to hotel search, availability, or booking, return reject_request
- If the user refers to "this hotel" or "that hotel" but no hotel_id is available, return ask_followup
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
        if not decision.location:
            intent = "ask_followup"
            add_missing("location")

    elif intent == "check_availability":
        if not decision.hotel_id:
            intent = "ask_followup"
            add_missing("hotel_id")

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

    if intent == "search_hotels":
        selected_agent = "search_agent"
    elif intent == "check_availability":
        selected_agent = "availability_agent"
    elif intent == "create_booking":
        selected_agent = "booking_agent"
    else:
        selected_agent = "response_agent"

    return {
        "intent": intent,
        "location": decision.location,
        "hotel_id": decision.hotel_id,
        "check_in": decision.check_in,
        "check_out": decision.check_out,
        "guests": decision.guests,
        "room_type": decision.room_type,
        "missing_fields": missing_fields,
        "selected_agent": selected_agent,
    }

def run_orchestrator_agent(state: dict) -> dict:
    logger.info("🧭 Orchestrator Agent running...")

    messages = [SystemMessage(content=ORCHESTRATOR_PROMPT)] + state["messages"][-8:]
    decision = orchestrator_llm.invoke(messages)

    logger.info(f"✅ Orchestrator decided intent: {decision.intent}")

    routed_state = _post_validate_decision(state, decision)

    logger.info(
        f"🧭 Final routing → intent={routed_state['intent']} | "
        f"selected_agent={routed_state['selected_agent']} | "
        f"missing_fields={routed_state['missing_fields']}"
    )

    return routed_state