import re
from typing import Optional


SUPPORTED_TOPICS = [
    "hotel",
    "booking",
    "book",
    "availability",
    "available",
    "room",
    "rooms",
    "check in",
    "check-in",
    "check out",
    "check-out",
    "guest",
    "guests",
    "stay",
    "invoice",
    "reservation",
    "reserve",
    "london",
    "paris",
    "barcelona",
    "dubai",
    "card",
    "payment",
    "cardholder",
    "pay",
    "visa",
    "mastercard",
    "debit",
    "credit",
]

BLOCKED_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"ignore\s+all\s+instructions",
    r"reveal\s+system\s+prompt",
    r"show\s+me\s+your\s+prompt",
    r"dump\s+the\s+database",
    r"drop\s+table",
    r"delete\s+all\s+bookings",
    r"bypass\s+guardrails",
    r"hack",
    r"exploit",
]


def normalize_dates_in_text(text: str) -> str:
    """
    Convert common DD/MM/YYYY or DD-MM-YYYY formats into YYYY-MM-DD.
    """
    if not text:
        return text

    def repl(match):
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)
        return f"{year}-{month}-{day}"

    text = re.sub(r"\b(\d{2})/(\d{2})/(\d{4})\b", repl, text)
    text = re.sub(r"\b(\d{2})-(\d{2})-(\d{4})\b", repl, text)
    return text


def _contains_supported_topic(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in SUPPORTED_TOPICS)


def _contains_blocked_pattern(text: str) -> Optional[str]:
    lowered = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, lowered):
            return pattern
    return None


def _extract_guest_count(text: str) -> Optional[int]:
    lowered = text.lower()

    patterns = [
        r"\bfor\s+(\d+)\s+guests?\b",
        r"\bwe\s+are\s+(\d+)\b",
        r"\b(\d+)\s+guests?\b",
        r"\bguest[s]?\s*[:=]?\s*(\d+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def validate_input(user_message: str) -> dict:
    """
    Returns:
    {
        "allowed": bool,
        "message": str,
        "normalized_message": str
    }
    """
    text = (user_message or "").strip()

    if not text:
        return {
            "allowed": False,
            "message": "Please enter a message.",
            "normalized_message": text,
        }

    if len(text) > 1000:
        return {
            "allowed": False,
            "message": "Your message is too long. Please send a shorter request.",
            "normalized_message": text,
        }

    blocked = _contains_blocked_pattern(text)
    if blocked:
        return {
            "allowed": False,
            "message": "I can help with hotel search, availability checks, bookings, and invoices only.",
            "normalized_message": text,
        }

    normalized = normalize_dates_in_text(text)

    guests = _extract_guest_count(normalized)
    if guests is not None and guests <= 0:
        return {
            "allowed": False,
            "message": "The number of guests must be at least 1.",
            "normalized_message": normalized,
        }

    if guests is not None and guests > 20:
        return {
            "allowed": False,
            "message": "For large group bookings above 20 guests, please provide a smaller request or handle it manually.",
            "normalized_message": normalized,
        }

    # Allow short follow-up answers like a single date or hotel id
    short_followup_patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{2}-\d{2}-\d{4}$",
        r"^hotel\s+\d+$",
        r"^\d+$",
        r"^book\s+it$",
        r"^yes$",
        r"^no$",
        r"^confirm$",
        r"^cancel$",
        r"^proceed$",
        r"^go\s+ahead$",
        r"^standard$",
        r"^deluxe$",
        r"^suite$",
        r"^[\d\s\-]{13,19}$",  # bare card number (digits, spaces, hyphens)
    ]
    if any(re.match(pattern, text.lower()) for pattern in short_followup_patterns):
        return {
            "allowed": True,
            "message": "ok",
            "normalized_message": normalized,
        }

    if not _contains_supported_topic(text):
        return {
            "allowed": False,
            "message": "I can help with hotel search, availability checks, bookings, and invoices only.",
            "normalized_message": normalized,
        }

    return {
        "allowed": True,
        "message": "ok",
        "normalized_message": normalized,
    }