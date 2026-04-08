from langchain.tools import tool

from backend.services.booking_service import create_booking_service


@tool
def create_booking(
    hotel_id: int,
    check_in: str,
    check_out: str,
    guests: int,
    user_name: str,
    user_email: str,
    room_type: str = None,
    payment_transaction_id: str = None,
) -> str:
    """
    Create a hotel booking and save it to the database.
    Provide room_type to book a specific room (e.g. Standard, Deluxe, Suite).
    Provide payment_transaction_id from the process_payment tool result.
    """
    result = create_booking_service(
        hotel_id=hotel_id,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        user_name=user_name,
        user_email=user_email,
        room_type=room_type,
        payment_transaction_id=payment_transaction_id,
    )

    if not result["success"]:
        return f"❌ Booking failed: {result['message']}"

    txn = result.get("payment_transaction_id") or "N/A"

    return (
        f"✅ Booking confirmed!\n"
        f"  Booking reference: {result['booking_reference']}\n"
        f"  Hotel            : {result['hotel_name']}\n"
        f"  Room type        : {result['room_type']}\n"
        f"  Check-in         : {result['check_in']}\n"
        f"  Check-out        : {result['check_out']}\n"
        f"  Guests           : {result['guests']}\n"
        f"  Price per night  : £{result['booked_price_per_night']:.2f}\n"
        f"  Total price      : £{result['total_price']:.2f} {result['currency']}\n"
        f"  Transaction ID   : {txn}\n"
        f"  Status           : {result['status']}"
    )
