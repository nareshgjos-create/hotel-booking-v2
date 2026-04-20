from langfuse import Langfuse
from backend.config import settings
from backend.utils.logger import logger


def get_langfuse_client():
    try:
        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL,
        )
        return client
    except Exception as e:
        logger.warning(f"Langfuse not available: {e}")
        return None


def _get_opik_client():
    """Return an Opik client or None if not configured."""
    try:
        if not settings.OPIK_API_KEY:
            return None
        import opik
        opik.configure(
            api_key=settings.OPIK_API_KEY,
            workspace=settings.OPIK_WORKSPACE or None,
            use_local=False,
        )
        return opik.Opik(project_name=settings.OPIK_PROJECT)
    except Exception as e:
        logger.warning(f"Opik not available: {e}")
        return None


def trace_langfuse(user_message: str, agent_response: str,
                   user_name: str = "", duration: float = 0.0):
    try:
        lf = get_langfuse_client()
        if not lf:
            return

        with lf.start_as_current_observation(name="hotel-agent-summary"):
            lf.update_current_span(
                input={"message": user_message},
                output={"response": agent_response},
                metadata={"user_name": user_name, "duration_seconds": round(duration, 3)},
            )
            trace_id = lf.get_current_trace_id()

        lf.flush()
        logger.info(f"✅ Langfuse: summary trace logged! trace_id={trace_id}")

    except Exception as e:
        logger.warning(f"Langfuse logging failed: {e}")


def trace_opik(user_message: str, agent_response: str,
               user_name: str = "", duration: float = 0.0):
    try:
        client = _get_opik_client()
        if not client:
            return

        trace = client.trace(
            name="hotel-agent-summary",
            input={"message": user_message},
            output={"response": agent_response},
            metadata={"user_name": user_name, "duration_seconds": round(duration, 3)},
        )
        client.flush()
        logger.info(f"✅ Opik: trace logged! trace_id={trace.id}")

    except Exception as e:
        logger.warning(f"Opik logging failed: {e}")


def trace_all(user_message: str, agent_response: str,
              user_name: str = "", duration: float = 0.0):
    logger.info("📊 Starting observability tracing...")
    trace_langfuse(user_message, agent_response, user_name, duration)
    trace_opik(user_message, agent_response, user_name, duration)
    logger.info("📊 Tracing complete!")
