import re

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage

from backend.utils.langfuse_compat import observe, langfuse_context
from backend.config import settings
from backend.tools.price_tools import calculate_price
from backend.tools.payment_tools import process_payment
from backend.tools.booking_tools import create_booking
from backend.utils.logger import logger


# ── Base LLM ──────────────────────────────────
_base_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0,
)

# One LLM per step — all tool-calling steps use tool_choice="required"
_price_llm          = _base_llm.bind_tools([calculate_price], tool_choice="required")
_process_pay_llm    = _base_llm.bind_tools([process_payment], tool_choice="required")
_create_booking_llm = _base_llm.bind_tools([create_booking],  tool_choice="required")
_chat_llm           = _base_llm  # no tools — plain text responses


# ── System Prompts ─────────────────────────────
_PRICE_PROMPT = """
You are the Booking Agent. The user has confirmed their booking.
Call calculate_price now using hotel_id, room_type, check_in, check_out, and guests
from the conversation history.
"""

_SHOW_PRICE_PROMPT = """
You are the Booking Agent. A price breakdown has just been calculated (see tool result above).
Present it clearly to the user, then ask them to provide:
1. Their card number
2. Cardholder name (name on the card)
Be friendly and concise.
"""

_PROCESS_PAYMENT_PROMPT = """
You are the Booking Agent handling payment.
The user has provided their card details in the conversation.
Extract the card number (digits only, ignore spaces/hyphens) and cardholder name
from the user's most recent message and call process_payment now.
Use the total amount and currency from the price breakdown earlier in the conversation.
"""

_CREATE_BOOKING_PROMPT = """
You are the Booking Agent. Payment was just approved (see tool result above).
Now call create_booking using:
- hotel_id, check_in, check_out, guests, room_type from the conversation history
- user_name: {user_name}
- user_email: {user_email}
- payment_transaction_id: {transaction_id}
"""

_CONFIRM_PROMPT = """
You are the Booking Agent. The payment and booking are complete (see tool results above).
Present a clear booking confirmation including:
- Booking reference
- Hotel name and room type
- Check-in and check-out dates
- Total amount charged
- Transaction ID
Keep it concise and professional.
"""


def _extract_transaction_id(messages: list) -> str:
    """Pull TXN-XXXX out of the most recent process_payment tool result."""
    for msg in reversed(messages):
        content = getattr(msg, "content", "") or ""
        match = re.search(r"TXN-[A-F0-9]{12}", content)
        if match:
            return match.group(0)
    return "N/A"


@observe(name="booking_agent")
def run_booking_agent(state: dict) -> dict:
    booking_step = state.get("booking_step") or ""
    user_name    = state.get("user_name", "")
    user_email   = state.get("user_email", "")

    langfuse_context.update_current_observation(
        input={"booking_step": booking_step},
    )
    logger.info(f"🛎️ Booking Agent running | booking_step='{booking_step}'")

    # ── Step 1: Calculate price ────────────────────────────────────────────────
    if booking_step == "":
        messages = [SystemMessage(content=_PRICE_PROMPT)] + state["messages"]
        response = _price_llm.invoke(messages)
        logger.info(f"🛎️ Step 1 — calculate_price | tool_calls={getattr(response, 'tool_calls', None)}")
        langfuse_context.update_current_observation(
            output={"step": "calculate_price", "tool_calls": getattr(response, "tool_calls", [])}
        )
        return {"messages": [response], "booking_step": "price_shown"}

    # ── Step 2: Show price, ask for card details ───────────────────────────────
    elif booking_step == "price_shown":
        messages = [SystemMessage(content=_SHOW_PRICE_PROMPT)] + state["messages"]
        response = _chat_llm.invoke(messages)
        logger.info("🛎️ Step 2 — showing price, requesting card details")
        langfuse_context.update_current_observation(
            output={"step": "show_price", "content": response.content}
        )
        return {"messages": [response], "booking_step": "awaiting_payment"}

    # ── Step 3: Process payment ────────────────────────────────────────────────
    elif booking_step == "awaiting_payment":
        messages = [SystemMessage(content=_PROCESS_PAYMENT_PROMPT)] + state["messages"]
        response = _process_pay_llm.invoke(messages)
        logger.info(f"🛎️ Step 3 — process_payment | tool_calls={getattr(response, 'tool_calls', None)}")
        langfuse_context.update_current_observation(
            output={"step": "process_payment", "tool_calls": getattr(response, "tool_calls", [])}
        )
        return {"messages": [response], "booking_step": "payment_done"}

    # ── Step 4: Create booking (after payment tool result is in messages) ──────
    elif booking_step == "payment_done":
        transaction_id = _extract_transaction_id(state["messages"])
        prompt = _CREATE_BOOKING_PROMPT.format(
            user_name=user_name,
            user_email=user_email,
            transaction_id=transaction_id,
        )
        messages = [SystemMessage(content=prompt)] + state["messages"]
        response = _create_booking_llm.invoke(messages)
        logger.info(f"🛎️ Step 4 — create_booking | txn={transaction_id} | tool_calls={getattr(response, 'tool_calls', None)}")
        langfuse_context.update_current_observation(
            output={"step": "create_booking", "transaction_id": transaction_id, "tool_calls": getattr(response, "tool_calls", [])}
        )
        return {"messages": [response], "booking_step": "done"}

    # ── Step 5: Generate confirmation message ──────────────────────────────────
    elif booking_step == "done":
        messages = [SystemMessage(content=_CONFIRM_PROMPT)] + state["messages"]
        response = _chat_llm.invoke(messages)
        logger.info("🛎️ Step 5 — booking complete, sending confirmation")
        langfuse_context.update_current_observation(
            output={"step": "confirmation", "content": response.content}
        )
        return {"messages": [response], "booking_step": ""}

    # ── Fallback ───────────────────────────────────────────────────────────────
    else:
        logger.warning(f"🛎️ Unknown booking_step '{booking_step}', resetting.")
        langfuse_context.update_current_observation(
            output={"step": "fallback", "booking_step": booking_step}
        )
        return {"messages": [], "booking_step": ""}
