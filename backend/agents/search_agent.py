from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from backend.tools.search_tools import search_hotels
from backend.config import settings
from backend.utils.logger import logger


search_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0
)

search_llm = search_llm.bind_tools(
    [search_hotels],
    tool_choice="auto"
)


SEARCH_AGENT_PROMPT = """
You are the Search Agent for a hotel system.

Your only responsibility is to search for hotels by location.
Use the search_hotels tool when a location is available.
If location is missing, ask for it briefly.
Do not handle availability or booking.
"""


def run_search_agent(state: dict, config: RunnableConfig = None):
    logger.info("🔍 Search Agent running...")

    messages = [
        SystemMessage(content=SEARCH_AGENT_PROMPT),
        *state["messages"]
    ]

    response = search_llm.invoke(messages, config=config)

    logger.info(f"🔍 Search Agent tool calls: {getattr(response, 'tool_calls', None)}")
    logger.info(f"🔍 Search Agent content: {response.content}")
    logger.info("✅ Search Agent finished")

    return {
        "messages": [response],
        "tool_last_called": "search_hotels"
    }