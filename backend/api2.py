from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.config import settings
from backend.services.hotel_service import (
    get_hotels_by_location,
    check_availability
)
from backend.utils.logger import logger
from backend.observability.tracing import trace_all
import time

app = FastAPI(
    title="Hotel Booking Agent API",
    description="Multi-agent hotel search system",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    message    : str
    user_name  : str = ""
    user_email : str = ""

@app.get("/")
def root():
    return {"message": "Hotel Booking Agent API is running 🏨"}

@app.get("/hotels")
def search_hotels(location: str):
    logger.info(f"Searching hotels in: {location}")
    hotels = get_hotels_by_location(location)
    if not hotels:
        raise HTTPException(
            status_code=404,
            detail=f"No hotels found in {location}"
        )
    return hotels

@app.get("/hotels/{hotel_id}")
def get_hotel(hotel_id: int):
    hotel = check_availability(hotel_id)
    if not hotel:
        raise HTTPException(
            status_code=404,
            detail=f"Hotel {hotel_id} not found"
        )
    return hotel

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        logger.info(f"Chat message: {req.message}")

        from backend.agents.graph import hotel_agent
        from langchain_core.messages import HumanMessage

        # ── Track time ────────────────────────
        start_time = time.time()

        result = hotel_agent.invoke({
            "messages"  : [HumanMessage(content=req.message)],
            "user_name" : req.user_name,
            "user_email": req.user_email,
            "location"  : "",
            "hotel_id"  : 0,
        })

        duration = time.time() - start_time
        last_message = result["messages"][-1]
        agent_response = last_message.content

        # ── Trace to MLflow + Langfuse ────────
        trace_all(
            user_message   = req.message,
            agent_response = agent_response,
            user_name      = req.user_name,
            duration       = duration
        )

        logger.info(f"✅ Response in {duration:.2f}s")
        return {"response": agent_response}

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))