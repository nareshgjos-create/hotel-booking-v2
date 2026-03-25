import mlflow
import os
mlflow.set_tracking_uri(f"file://{os.path.abspath('mlruns')}")
from datetime import datetime
from mlflow.tracking import MlflowClient
from langfuse import Langfuse
from backend.config import settings
from backend.utils.logger import logger

# ── MLflow Setup ─────────────────────────────
EXPERIMENT_NAME = "hotel-booking-agent-v2"

def setup_mlflow():
    """
    WHY: Creates or gets the MLflow experiment
    Handles deleted experiments gracefully!
    """
    try:
        client = MlflowClient()
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)

        if experiment is None:
            # Create new experiment
            mlflow.set_experiment(EXPERIMENT_NAME)
            logger.info(f"✅ MLflow: Created experiment '{EXPERIMENT_NAME}'")

        elif experiment.lifecycle_stage == "deleted":
            # Use Default if deleted
            mlflow.set_experiment("Default")
            logger.info("✅ MLflow: Using Default experiment")

        else:
            # Use existing experiment
            mlflow.set_experiment(EXPERIMENT_NAME)
            logger.info(f"✅ MLflow: Using experiment '{EXPERIMENT_NAME}'")

    except Exception as e:
        logger.warning(f"MLflow setup failed: {e}")

# Run setup on import
setup_mlflow()

# ── Langfuse Setup ────────────────────────────
def get_langfuse_client():
    """
    WHY: Creates Langfuse client for cloud tracing
    """
    try:
        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST
        )
        logger.info("✅ Langfuse client created!")
        return client
    except Exception as e:
        logger.warning(f"Langfuse not available: {e}")
        return None


def trace_agent_run(user_message: str, agent_response: str,
                    user_name: str = "", duration: float = 0.0):
    """
    WHY: Logs every agent interaction to MLflow
    So we can see all runs in the MLflow dashboard!
    """
    try:
        with mlflow.start_run(
            run_name=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ):
            # Log parameters
            mlflow.log_param("user_name",    user_name)
            mlflow.log_param("user_message", user_message[:100])

            # Log metrics
            mlflow.log_metric("response_length",  len(agent_response))
            mlflow.log_metric("duration_seconds",  duration)

            # Log conversation as artifact
            mlflow.log_text(
                f"User : {user_message}\nAgent: {agent_response}\nTime : {duration:.2f}s",
                "conversation.txt"
            )
            logger.info(f"✅ MLflow: logged run! Duration: {duration:.2f}s")

    except Exception as e:
        logger.warning(f"MLflow logging failed: {e}")


def trace_langfuse(user_message: str, agent_response: str,
                   user_name: str = ""):
    """
    WHY: Traces every LLM interaction to Langfuse cloud
    So we can see token usage, costs, and performance!
    """
    try:
        langfuse = get_langfuse_client()
        if not langfuse:
            return

        langfuse.create_event(
            name="hotel-agent-chat",
            input={
                "user_message": user_message,
                "user_name"   : user_name
            },
            output={
                "agent_response": agent_response
            }
        )
        langfuse.flush()
        logger.info("✅ Langfuse: trace logged!")

    except Exception as e:
        logger.warning(f"Langfuse logging failed: {e}")


def trace_all(user_message: str, agent_response: str,
              user_name: str = "", duration: float = 0.0):
    """
    WHY: Logs to BOTH MLflow and Langfuse at once!
    One function call → traces everywhere!
    """
    logger.info("📊 Starting observability tracing...")
    trace_agent_run(user_message, agent_response, user_name, duration)
    trace_langfuse(user_message, agent_response, user_name)
    logger.info("📊 Tracing complete!")