from typing import Annotated, List, Optional, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HotelAgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]

    user_name: str
    user_email: str

    intent: Literal[
        "search_hotels",
        "check_availability",
        "create_booking",
        "ask_followup",
        "reject_request",
    ]
    selected_agent: Optional[str]

    location: Optional[str]
    hotel_id: Optional[int]
    check_in: Optional[str]
    check_out: Optional[str]
    guests: Optional[int]
    room_type: Optional[str]

    missing_fields: List[str]
    guardrail_flags: List[str]
    policy_decision: Literal["allow", "clarify", "block"]

    tool_last_called: Optional[str]
    tool_result: Optional[str]

    booking_reference: Optional[str]