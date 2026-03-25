from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from backend.tools.booking_tools import create_booking
from backend.config import settings
from backend.utils.logger import logger


booking_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0
)

booking_llm = booking_llm.bind_tools(
    [create_booking],
    tool_choice="auto"
)


BOOKING_PROMPT = """
You are the Hotel Booking Agent.

Your responsibility:
- Create hotel bookings using the booking tool

Required:
- hotel_id
- room_type_id
- check_in
- check_out
- guests
- user_name
- user_email

Rules:
- Never call the booking tool if any required field is missing
- Never invent booking data
- If any field is missing, ask the user for the missing fields clearly
- Only confirm a booking after the tool succeeds
"""


def run_booking_agent(state: dict, config: RunnableConfig = None):
    logger.info("🛎️ Booking Agent running...")

    booking_context = f"""
Known booking state:
hotel_id={state.get('hotel_id')}
room_type={state.get('room_type')}
room_type_id={state.get('room_type_id')}
check_in={state.get('check_in')}
check_out={state.get('check_out')}
guests={state.get('guests')}
user_name={state.get('user_name')}
user_email={state.get('user_email')}
"""

    messages = [
        SystemMessage(content=BOOKING_PROMPT + "\n\n" + booking_context),
        *state["messages"][-6:]
    ]

    response = booking_llm.invoke(messages, config=config)

    logger.info(f"🛎️ Booking Agent tool calls: {getattr(response,'tool_calls',None)}")
    logger.info("✅ Booking Agent finished")

    return {
        "messages": [response],
        "tool_last_called": "create_booking"
    }