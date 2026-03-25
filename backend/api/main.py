from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, ToolMessage
from backend.graph.graph import hotel_agent
from backend.utils.logger import logger

app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    user_name: str = ""
    user_email: str = ""


@app.post("/chat")
def chat(request: ChatRequest):
    logger.info("📩 /chat request received")

    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_name": request.user_name,
        "user_email": request.user_email,
        "location": "",
        "hotel_id": None
    }

    result = hotel_agent.invoke(initial_state)

    logger.info(f"📦 Total messages returned by graph: {len(result['messages'])}")

    for i, msg in enumerate(result["messages"]):
        logger.info(
            f"Message {i} | type={type(msg).__name__} | content={repr(getattr(msg, 'content', None))}"
        )

    # 1) Prefer actual tool output first
    for msg in reversed(result["messages"]):
        if isinstance(msg, ToolMessage):
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                logger.info("✅ Returning ToolMessage content")
                return {"response": content}

    # 2) Otherwise return last non-human non-empty message
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip() and not isinstance(msg, HumanMessage):
            logger.info("✅ Returning non-human message content")
            return {"response": content}

    logger.warning("⚠️ No valid response found in graph output")
    return {"response": "Sorry, I couldn't find a valid response."}