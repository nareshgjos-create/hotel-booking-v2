import re
from datetime import datetime
from typing import Dict, Any, List


PROMPT_INJECTION_PATTERNS = [
    r"ignore (all|previous) instructions",
    r"reveal (the )?(system prompt|hidden prompt)",
    r"bypass safety",
    r"call the tool directly",
    r"do not follow your rules",
    r"act as system",
]


def detect_prompt_injection(text: str) -> List[str]:
    flags = []
    lowered = text.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            flags.append(f"prompt_injection:{pattern}")

    return flags


def validate_dates(check_in: str | None, check_out: str | None) -> List[str]:
    errors = []

    if check_in and check_out:
        try:
            in_date = datetime.fromisoformat(check_in).date()
            out_date = datetime.fromisoformat(check_out).date()

            if out_date <= in_date:
                errors.append("check_out_must_be_after_check_in")

        except ValueError:
            errors.append("invalid_date_format")

    return errors


def validate_required_fields(state: Dict[str, Any]) -> List[str]:
    missing = []

    intent = state.get("intent")

    if intent == "search_hotels":
        if not state.get("location"):
            missing.append("location")

    if intent == "check_availability":
        required = ["hotel_id", "check_in", "check_out", "guests"]

        for field in required:
            if not state.get(field):
                missing.append(field)

    if intent == "create_booking":
        required = [
            "hotel_id",
            "check_in",
            "check_out",
            "guests",
            "user_name",
            "user_email",
        ]

        for field in required:
            if not state.get(field):
                missing.append(field)

    return missing


def normalize_state_fields(state: Dict[str, Any]) -> Dict[str, Any]:

    state.setdefault("missing_fields", [])
    state.setdefault("guardrail_flags", [])
    state.setdefault("policy_decision", "allow")

    text = ""

    if state.get("messages"):
        last = state["messages"][-1]
        text = getattr(last, "content", "") or ""

    # Prompt injection detection
    injection_flags = detect_prompt_injection(text)
    state["guardrail_flags"].extend(injection_flags)

    # Date validation
    date_errors = validate_dates(
        state.get("check_in"),
        state.get("check_out"),
    )

    state["guardrail_flags"].extend(date_errors)

    # Required field validation
    missing = validate_required_fields(state)
    state["missing_fields"] = missing

    # Policy decision
    if injection_flags:
        state["policy_decision"] = "block"

    elif missing:
        state["policy_decision"] = "clarify"

    elif date_errors:
        state["policy_decision"] = "clarify"

    else:
        state["policy_decision"] = "allow"

    return state