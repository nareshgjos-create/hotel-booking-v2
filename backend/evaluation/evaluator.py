"""
LLM-as-Judge Evaluator
======================
Automatically evaluates every agent response on three dimensions:
  - relevance   : Is the response relevant to the user's query?
  - helpfulness : Is the response helpful and actionable?
  - accuracy    : Does the response appear accurate (no hallucinations)?

Scores (0.0 – 1.0) are posted to both Langfuse and Opik.
"""
import json

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from langfuse import Langfuse

from backend.config import settings
from backend.utils.logger import logger


# ── Judge LLM ─────────────────────────────────────────────────────────────────
_judge_llm = AzureChatOpenAI(
    azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_OPENAI_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    temperature=0,
)

_EVAL_PROMPT = """\
You are an impartial evaluation judge for a hotel booking AI assistant.

Given the user's message and the agent's response, rate each dimension on a
scale of 0.0 to 1.0:
  - relevance   : How relevant is the response to the user's query?
  - helpfulness : How helpful and actionable is the response?
  - accuracy    : Does the response appear accurate with no hallucinated
                  hotel names, prices, or booking details?

User message   : {user_message}
Agent response : {agent_response}

Respond ONLY with valid JSON — no markdown, no extra text:
{{"relevance": <float 0-1>, "helpfulness": <float 0-1>, "accuracy": <float 0-1>, "comment": "<one sentence justification>"}}
"""

_SCORE_NAMES = ["relevance", "helpfulness", "accuracy"]


# ── Langfuse client ────────────────────────────────────────────────────────────
def _get_langfuse() -> Langfuse | None:
    try:
        return Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL,
        )
    except Exception:
        return None


# ── Opik client ────────────────────────────────────────────────────────────────
def _get_opik():
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


# ── Public API ─────────────────────────────────────────────────────────────────
def evaluate_response(
    user_message: str,
    agent_response: str,
    trace_id: str | None = None,
) -> dict:
    """
    LLM-as-Judge evaluation.
    Posts scores to Langfuse (via trace_id) and Opik.
    Returns the raw scores dict (or {} on failure).
    """
    try:
        prompt = _EVAL_PROMPT.format(
            user_message=user_message,
            agent_response=agent_response,
        )
        result = _judge_llm.invoke([HumanMessage(content=prompt)])
        raw = result.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        scores = json.loads(raw)

        logger.info(
            f"📊 Evaluation — relevance={scores.get('relevance')}, "
            f"helpfulness={scores.get('helpfulness')}, "
            f"accuracy={scores.get('accuracy')} | {scores.get('comment', '')}"
        )

        # ── Post scores to Langfuse ────────────────────────────────────────
        if trace_id:
            langfuse = _get_langfuse()
            if langfuse:
                comment = scores.get("comment", "")
                for metric in _SCORE_NAMES:
                    if metric in scores:
                        langfuse.create_score(
                            trace_id=trace_id,
                            name=metric,
                            value=float(scores[metric]),
                            comment=comment,
                        )
                langfuse.flush()
                logger.info(f"✅ Langfuse: scores posted to trace {trace_id}")

        # ── Post scores to Opik ────────────────────────────────────────────
        opik_client = _get_opik()
        if opik_client:
            try:
                trace = opik_client.trace(
                    name="llm-judge-evaluation",
                    input={"user_message": user_message},
                    output={"agent_response": agent_response},
                    metadata={
                        "relevance":   scores.get("relevance"),
                        "helpfulness": scores.get("helpfulness"),
                        "accuracy":    scores.get("accuracy"),
                        "comment":     scores.get("comment", ""),
                    },
                )
                for metric in _SCORE_NAMES:
                    if metric in scores:
                        opik_client.create_score(
                            trace_id=trace.id,
                            name=metric,
                            value=float(scores[metric]),
                        )
                opik_client.flush()
                logger.info(f"✅ Opik: evaluation scores posted to trace {trace.id}")
            except Exception as e:
                logger.warning(f"Opik evaluation posting failed: {e}")

        return scores

    except Exception as e:
        logger.warning(f"⚠️ Evaluation failed: {e}")
        return {}
