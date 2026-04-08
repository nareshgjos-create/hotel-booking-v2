from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from backend.utils.langfuse_compat import observe, langfuse_context

from backend.config import settings
from backend.tools.search_tools import search_hotels
from backend.tools.availability_tools import check_hotel_availability
from backend.utils.logger import logger


search_availability_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0
).bind_tools(
    [
        search_hotels,
        check_hotel_availability
    ],
    tool_choice="auto"
)


SEARCH_AVAILABILITY_PROMPT = """
You are the Hotel Search & Availability Agent.

Your responsibilities:
- Search hotels by location
- Check hotel availability
- Decide which tool to use

Tools:
1. search_hotels → use when user asks to find hotels
2. check_hotel_availability → use when user asks for availability

Rules:
- Always use tools for real data
- Never invent hotels
- Never invent availability
- Ask for missing information when needed

Search requires:
- location

Availability requires:
- hotel_id
- check_in
- check_out
- guests

Behavior:
- If user asks "Find hotel in London" → search_hotels
- If user asks "Check availability" → check_hotel_availability
- If user provides partial info → ask for missing fields

Be concise and structured.
"""


@observe(name="search_availability_agent")
def run_search_availability_agent(state: dict):
    langfuse_context.update_current_observation(
        input={"last_message": state["messages"][-1].content if state["messages"] else ""},
    )
    logger.info("🏨 Search & Availability Agent running...")

    messages = [
        SystemMessage(content=SEARCH_AVAILABILITY_PROMPT),
        *state["messages"]
    ]

    response = search_availability_llm.invoke(messages)

    langfuse_context.update_current_observation(
        output={"content": response.content, "tool_calls": getattr(response, "tool_calls", [])},
    )

    logger.info(f"🏨 Tool calls: {getattr(response, 'tool_calls', None)}")
    logger.info(f"🏨 Content: {response.content}")
    logger.info("✅ Search & Availability Agent finished")

    return {
        "messages": [response]
    }