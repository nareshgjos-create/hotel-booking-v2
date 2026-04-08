"""
LLM-as-Judge Evaluator
======================
Automatically evaluates every agent response on three dimensions:
  - relevance   : Is the response relevant to the user's query?
  - helpfulness : Is the response helpful and actionable?
  - accuracy    : Does the response appear accurate (no hallucinations)?

Scores (0.0 – 1.0) are posted directly to Langfuse via trace_id so they
appear on the trace in the Langfuse dashboard.
"""
import json

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from langfuse import Langfuse

from backend.config import settings
from backend.utils.logger import logger


# ── Judge LLM (same deployment, temperature=0 for consistency) ────────────────
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


# ── Public API ─────────────────────────────────────────────────────────────────
def evaluate_response(
    user_message: str,
    agent_response: str,
    trace_id: str | None = None,
) -> dict:
    """
    LLM-as-Judge evaluation.

    1. Asks the judge LLM to score relevance / helpfulness / accuracy.
    2. Posts all three scores to the Langfuse trace identified by trace_id.

    Returns the raw scores dict (or {} on failure).
    """
    try:
        prompt = _EVAL_PROMPT.format(
            user_message=user_message,
            agent_response=agent_response,
        )
        result = _judge_llm.invoke([HumanMessage(content=prompt)])
        raw = result.content.strip()

        # Strip markdown code fence if the LLM wraps the JSON
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
                logger.info(f"✅ Langfuse: evaluation scores posted to trace {trace_id}")

        return scores

    except Exception as e:
        logger.warning(f"⚠️ Evaluation failed: {e}")
        return {}
