import time
from langchain.tools import tool

from backend.services.payment_service import process_payment_service
from backend.utils.langfuse_compat import langfuse_context


@tool
def process_payment(
    amount: float,
    currency: str,
    card_number: str,
    cardholder_name: str,
) -> str:
    """
    Process a payment for a hotel booking (simulated).
    Requires the total amount, currency, card number, and cardholder name.
    Returns a transaction ID on success.
    """
    start = time.time()

    langfuse_context.update_current_observation(
        input={"amount": amount, "currency": currency, "cardholder_name": cardholder_name}
    )

    result = process_payment_service(
        amount=amount,
        currency=currency,
        card_number=card_number,
        cardholder_name=cardholder_name,
    )

    elapsed = round(time.time() - start, 3)

    if not result["success"]:
        langfuse_context.update_current_observation(
            output={"success": False, "message": result["message"], "latency_s": elapsed}
        )
        return f"❌ Payment failed: {result['message']}"

    output = (
        f"✅ Payment approved!\n"
        f"  Transaction ID : {result['transaction_id']}\n"
        f"  Amount charged : £{result['amount']:.2f} {result['currency']}\n"
        f"  Card ending    : ****{result['card_last4']}\n"
        f"  Cardholder     : {result['cardholder_name']}"
    )

    langfuse_context.update_current_observation(
        output={"success": True, "transaction_id": result["transaction_id"], "latency_s": elapsed}
    )

    return output
