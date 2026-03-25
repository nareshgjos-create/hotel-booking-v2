from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from backend.config import settings
from backend.tools.availability_tools import check_hotel_availability
from backend.utils.logger import logger

availability_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0
).bind_tools([check_hotel_availability])

AVAILABILITY_AGENT_PROMPT = """
You are the Hotel Availability Agent.

Your responsibility:
- Check hotel room availability using the tool
- Return available room types for the requested stay

Required inputs:
- hotel_id
- check_in (YYYY-MM-DD)
- check_out (YYYY-MM-DD)
- guests

Rules:
- Always use the tool when all required fields are available
- Never invent hotel availability
- Never invent room types
- If information is missing, ask the user for it
- Only report availability based on tool output

Behavior:
- If rooms are available, return the available room types
- If no rooms available, clearly say no availability
- Be concise and structured

You must use the tool to check availability.
"""

def run_availability_agent(state: dict) -> dict:
    logger.info("📅 Availability Agent running...")

    messages = [SystemMessage(content=AVAILABILITY_AGENT_PROMPT)] + state["messages"]
    response = availability_llm.invoke(messages)

    logger.info("✅ Availability Agent done!")
    return {"messages": [response]}