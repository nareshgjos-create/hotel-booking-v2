from langchain.tools import tool
from backend.services.booking_service import create_booking_service


@tool
def create_booking(
    hotel_id: int,
    check_in: str,
    check_out: str,
    guests: int,
    user_name: str,
    user_email: str
):
    """
    Create hotel booking
    """

    result = create_booking_service(
        hotel_id=hotel_id,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        user_name=user_name,
        user_email=user_email
    )

    return result