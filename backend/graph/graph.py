
from dotenv import load_dotenv
load_dotenv()
from backend.agents.orchestrator_agent import run_orchestrator_agent
import re
from datetime import datetime
from typing import Annotated, List
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from backend.agents.search_agent import run_search_agent
from backend.agents.availability_agent import run_availability_agent
from backend.agents.booking_agent import run_booking_agent

from backend.tools.search_tools import search_hotels
from backend.tools.availability_tools import check_hotel_availability
from backend.tools.booking_tools import create_booking

from backend.utils.logger import logger
from langchain_core.messages import AIMessage

class HotelAgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    user_name: str
    user_email: str
    location: str
    hotel_id: int
    room_type: str
    room_type_id: int
    check_in: str
    check_out: str
    guests: int
    intent: str
    missing_fields: list[str]
    selected_agent: str

search_tool_node = ToolNode([search_hotels])
availability_tool_node = ToolNode([check_hotel_availability])
booking_tool_node = ToolNode([create_booking])


def _last_user_message_text(state: HotelAgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content.lower()
    return ""


def extract_booking_context(state: HotelAgentState) -> dict:
    text = _last_user_message_text(state)
    updates = {}

    hotel_match = re.search(r"\bhotel\s+(\d+)\b", text)
    if hotel_match:
        updates["hotel_id"] = int(hotel_match.group(1))

    guests_match = re.search(r"\b(\d+)\s*(people|person|guests|guest)\b", text)
    if guests_match:
        updates["guests"] = int(guests_match.group(1))
    else:
        fallback_guests = re.search(r"\bfor\s+(\d+)\b", text)
        if fallback_guests:
            updates["guests"] = int(fallback_guests.group(1))

    room_type_map = {
    "standard": 1,
    "deluxe": 2,
    "suite": 3,
            }

    for rt, rt_id in room_type_map.items():
        if rt in text:
            updates["room_type"] = rt.title()
            updates["room_type_id"] = rt_id
            break

    for loc in ["london", "paris", "barcelona", "dubai"]:
        if loc in text:
            updates["location"] = loc.title()
            break

    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    if email_match:
        updates["user_email"] = email_match.group(0)

    raw_dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", text)
    parsed_dates = []

    for d in raw_dates:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                parsed_dates.append(datetime.strptime(d, fmt).strftime("%Y-%m-%d"))
                break
            except ValueError:
                pass

    if len(parsed_dates) >= 2:
        updates["check_in"] = parsed_dates[0]
        updates["check_out"] = parsed_dates[1]

    if updates:
        logger.info(f"🧠 Extracted state updates: {updates}")

    return updates

def route_after_orchestrator(state: HotelAgentState) -> str:
    logger.info(f"🔥 DEBUG selected_agent raw value = {state.get('selected_agent')!r}")
    selected = state.get("selected_agent", "search_agent")
    logger.info(f"🧭 Orchestrator routing to: {selected}")
    return selected

def build_followup_response(state: HotelAgentState) -> dict:
    missing = state.get("missing_fields", [])
    if missing:
        return {
            "messages": [
                AIMessage(content=f"I still need the following to complete your request: {', '.join(missing)}.")
            ]
        }
    return {
        "messages": [
            AIMessage(content="I need a bit more information to continue.")
        ]
    }

def should_search_agent_continue(state: HotelAgentState) -> str:
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("Search Agent wants to use search tool")
        return "search_tools"

    logger.info("Search Agent finished")
    return END

def route_after_availability_agent(state: HotelAgentState) -> str:
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("Availability Agent wants to use availability tool")
        return "availability_tools"

    logger.info("Availability Agent finished")
    return END


def should_booking_agent_continue(state: HotelAgentState) -> str:
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("Booking Agent wants to use booking tool")
        return "booking_tools"

    logger.info("Booking Agent finished")
    return END


def build_graph():
    graph = StateGraph(HotelAgentState)

    graph.add_node("extract_context", extract_booking_context)
    graph.add_node("orchestrator_agent", run_orchestrator_agent)
    graph.add_node("search_agent", run_search_agent)
    graph.add_node("availability_agent", run_availability_agent)
    graph.add_node("booking_agent", run_booking_agent)
    graph.add_node("response_agent", build_followup_response)
    
    graph.add_node("search_tools", search_tool_node)
    graph.add_node("availability_tools", availability_tool_node)
    graph.add_node("booking_tools", booking_tool_node)

    graph.set_entry_point("extract_context")
    graph.add_edge("extract_context", "orchestrator_agent")
    graph.add_edge("response_agent", END)
    graph.add_conditional_edges(
        "orchestrator_agent",
        route_after_orchestrator,
        {
            "search_agent": "search_agent",
            "availability_agent": "availability_agent",
            "booking_agent": "booking_agent",
            "response_agent": "response_agent",
        },
    )

    graph.add_conditional_edges(
        "search_agent",
        should_search_agent_continue,
        {
            "search_tools": "search_tools",
            END: END,
        },
    )
    graph.add_edge("search_tools", "search_agent")

    graph.add_conditional_edges(
        "availability_agent",
        route_after_availability_agent,
        {
            "availability_tools": "availability_tools",
            END: END,
        },
    )
    graph.add_edge("availability_tools", "availability_agent")

    graph.add_conditional_edges(
        "booking_agent",
        should_booking_agent_continue,
        {
            "booking_tools": "booking_tools",
            END: END,
        },
    )
    graph.add_edge("booking_tools", "booking_agent")

    return graph.compile()

hotel_agent = build_graph()
logger.info("✅ Hotel Agent Graph built successfully!")