from dotenv import load_dotenv
load_dotenv()

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from backend.agents.search_availability_agent import run_search_availability_agent
from backend.agents.booking_agent import run_booking_agent
from backend.agents.orchestrator_agent import run_orchestrator_agent
from backend.agents.invoice_agent import run_invoice_agent

from backend.tools.search_tools import search_hotels
from backend.tools.availability_tools import check_hotel_availability
from backend.tools.booking_tools import create_booking
from backend.tools.price_tools import calculate_price
from backend.tools.payment_tools import process_payment

from backend.utils.logger import logger


# ── State ─────────────────────────────────────
class HotelAgentState(TypedDict):

    messages: Annotated[List[BaseMessage], add_messages]

    user_name: str
    user_email: str

    location: str
    hotel_id: int
    check_in: str
    check_out: str
    guests: int
    room_type: str

    intent: str
    selected_agent: str
    missing_fields: list

    # Booking flow state
    booking_step: str
    payment_transaction_id: Optional[str]

    # Invoice flow state
    invoice_file_path: Optional[str]


# ── Tool Nodes ────────────────────────────────
search_availability_tools = ToolNode([
    search_hotels,
    check_hotel_availability,
])

booking_tool_node = ToolNode([
    calculate_price,
    process_payment,
    create_booking,
])


# ── Orchestrator Router ───────────────────────
def route_after_orchestrator(state: HotelAgentState):

    # If we're mid-booking flow, bypass orchestrator routing
    if state.get("booking_step") in ("price_shown", "awaiting_payment", "payment_done", "done"):
        logger.info(f"🧭 Bypassing orchestrator — booking_step='{state.get('booking_step')}'")
        return "booking_agent"

    agent = state.get("selected_agent")

    logger.info(f"🧭 Routing after orchestrator with intent: {state.get('intent')}")

    if agent == "search_availability_agent":
        return "search_availability_agent"

    if agent == "booking_agent":
        return "booking_agent"

    if agent == "invoice_agent":
        return "invoice_agent"

    return END


# ── Tool Routing ──────────────────────────────
def should_continue_booking(state: HotelAgentState):
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END


def should_continue_search(state: HotelAgentState):
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END


# ── Build Graph ───────────────────────────────
def build_graph():

    graph = StateGraph(HotelAgentState)

    # ── Nodes ─────────────────────────────
    graph.add_node("orchestrator", run_orchestrator_agent)
    graph.add_node("search_availability_agent", run_search_availability_agent)
    graph.add_node("booking_agent", run_booking_agent)
    graph.add_node("invoice_agent", run_invoice_agent)
    graph.add_node("search_availability_tools", search_availability_tools)
    graph.add_node("booking_tools", booking_tool_node)

    # ── Entry Point ───────────────────────
    graph.set_entry_point("orchestrator")

    # ── Orchestrator Routing ──────────────
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "search_availability_agent": "search_availability_agent",
            "booking_agent": "booking_agent",
            "invoice_agent": "invoice_agent",
            END: END,
        },
    )

    # ── Search + Availability Agent ───────
    graph.add_conditional_edges(
        "search_availability_agent",
        should_continue_search,
        {
            "tools": "search_availability_tools",
            END: END,
        },
    )

    graph.add_edge("search_availability_tools", END)

    # ── Booking Agent (loops back after each tool call) ────────────────────────
    graph.add_conditional_edges(
        "booking_agent",
        should_continue_booking,
        {
            "tools": "booking_tools",
            END: END,
        },
    )

    # Loop: after tools run, return to booking_agent for next step
    graph.add_edge("booking_tools", "booking_agent")

    # Invoice agent goes directly to END
    graph.add_edge("invoice_agent", END)

    return graph.compile()


# ── Create Agent ─────────────────────────────
hotel_agent = build_graph()

logger.info("✅ Hotel Agent Graph built successfully!")
