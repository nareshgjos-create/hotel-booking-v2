import os

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Annotated, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from backend.tools.extract_invoice_data import extract_invoice_data
from backend.tools.check_payment_status import check_payment_status
from backend.tools.lookup_company_contact import lookup_company_contact
from backend.config import settings
from backend.utils.logger import logger

TOOLS = [extract_invoice_data, check_payment_status, lookup_company_contact]

SYSTEM_PROMPT = """You are an Invoice Processing Orchestration Agent.

When given an invoice file path, you MUST perform ALL THREE steps in this exact order:

1. Call `extract_invoice_data` with the provided file_path to extract structured data.
2. Call `check_payment_status` using the invoice_number obtained from step 1.
3. Call `lookup_company_contact` using the vendor_name obtained from step 1.

After completing all three tool calls, provide a concise summary covering:
- Invoice details (number, vendor, date, total amount)
- Current payment status and amounts
- Vendor contact information

Always complete all three tool calls before writing your final summary."""


class InvoiceAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


def _build_invoice_graph():
    llm = AzureChatOpenAI(
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=0,
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: InvoiceAgentState) -> dict:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(TOOLS)

    graph = StateGraph(InvoiceAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


_invoice_graph = _build_invoice_graph()


def run_invoice_agent(state: dict) -> dict:
    logger.info("🧾 Invoice Agent running...")

    file_path = state.get("invoice_file_path", "")
    if not file_path:
        return {"messages": state["messages"]}

    result = _invoice_graph.invoke({
        "messages": [HumanMessage(content=f"Process this invoice: {file_path}")]
    })

    logger.info("✅ Invoice Agent completed.")
    return {"messages": result["messages"]}
