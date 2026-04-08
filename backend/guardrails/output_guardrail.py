from typing import Optional


SENSITIVE_OUTPUT_PATTERNS = [
    "traceback",
    "exception in asgi application",
    "openai.badrequesterror",
    "sqlalchemy.exc",
    "psycopg2.errors",
    "langgraph",
    "tool_calls",
    "system prompt",
    "api_key",
    "secret_key",
]


def sanitize_output(reply: Optional[str]) -> str:
    """
    Clean final response before sending it to the frontend.
    """
    if not reply or not str(reply).strip():
        return "Sorry, I couldn't generate a valid response."

    text = str(reply).strip()
    lowered = text.lower()

    if any(pattern in lowered for pattern in SENSITIVE_OUTPUT_PATTERNS):
        return "Sorry, something went wrong while processing your request. Please try again."

    if len(text) > 4000:
        return text[:4000].rstrip() + "\n\n[response truncated]"

    return text


def sanitize_error_message(_: Exception) -> str:
    """
    Safe fallback for unexpected backend errors.
    """
    return "Sorry, something went wrong while processing your request. Please try again."