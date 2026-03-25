import uuid


def create_booking_service(
    hotel_id: int,
    check_in: str,
    check_out: str,
    guests: int,
    user_name: str,
    user_email: str
):
    booking_reference = f"BK-{uuid.uuid4().hex[:8].upper()}"

    return {
        "booking_reference": booking_reference,
        "hotel_id": hotel_id,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "user_name": user_name,
        "user_email": user_email,
        "status": "confirmed"
    }