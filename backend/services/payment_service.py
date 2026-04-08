import uuid


def process_payment_service(
    amount: float,
    currency: str,
    card_number: str,
    cardholder_name: str,
) -> dict:
    digits = card_number.replace(" ", "").replace("-", "")

    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return {
            "success": False,
            "message": "Invalid card number. Please provide a valid 13-19 digit card number.",
        }

    if not cardholder_name.strip():
        return {"success": False, "message": "Cardholder name cannot be empty."}

    transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    return {
        "success": True,
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "card_last4": digits[-4:],
        "cardholder_name": cardholder_name.strip(),
        "status": "approved",
    }
